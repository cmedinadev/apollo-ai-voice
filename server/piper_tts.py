import subprocess
import os
import tempfile
from pathlib import Path
import time

class PiperTTSAdvanced:
    def __init__(self, model_path="../piper/models/pt_BR-faber-medium.onnx"):
        self.model_path = os.path.expanduser(model_path)
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Modelo não encontrado: {self.model_path}")
        
        # Verifica se FFmpeg está instalado
        self.has_ffmpeg = self._check_ffmpeg()
        # Verifica se SoX está instalado (melhor para pitch)
        self.has_sox = self._check_sox()
    
    def _check_ffmpeg(self):
        """Verifica se FFmpeg está disponível"""
        try:
            subprocess.run(["ffmpeg", "-version"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            print("⚠️  FFmpeg não encontrado. Instale com: brew install ffmpeg")
            return False
    
    def _check_sox(self):
        """Verifica se SoX está disponível"""
        try:
            subprocess.run(["sox", "--version"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            return False
    
    def synthesize(self, text, output_file="output.wav", 
                   length_scale=1.0, noise_scale=0.667, noise_w=0.8):
        """Sintetiza texto básico"""
        cmd = [
            "piper",
            "--model", self.model_path,
            "--length_scale", str(length_scale),
            "--noise_scale", str(noise_scale),
            "--noise_w", str(noise_w),
            "--output_file", output_file,
            "", text  # Usando --text ao invés de stdin
        ]
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                print(f"✗ Erro: {result.stderr}")
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"✗ Erro: {e}")
            return False
    
    def adjust_pitch(self, input_file, output_file, pitch_factor=1.3, preserve_tempo=True):
        """
        Ajusta o pitch do áudio usando FFmpeg mantendo o tempo
        
        Args:
            input_file: Arquivo de entrada
            output_file: Arquivo de saída
            pitch_factor: Fator de pitch (1.0 = normal, >1.0 = mais agudo)
            preserve_tempo: Se True, mantém a velocidade original
        """
        if not self.has_ffmpeg:
            print("✗ FFmpeg necessário para ajuste de pitch")
            return False
        
        if preserve_tempo:
            # Calcula tempo de compensação
            tempo = 1.0 / pitch_factor
            
            # atempo só aceita valores entre 0.5 e 2.0
            # Se estiver fora do range, aplica múltiplas vezes
            atempo_filters = []
            current_tempo = tempo
            
            while current_tempo < 0.5:
                atempo_filters.append("atempo=0.5")
                current_tempo /= 0.5
            
            while current_tempo > 2.0:
                atempo_filters.append("atempo=2.0")
                current_tempo /= 2.0
            
            if 0.5 <= current_tempo <= 2.0:
                atempo_filters.append(f"atempo={current_tempo}")
            
            # Monta o filtro completo
            atempo_chain = ",".join(atempo_filters)
            filter_str = f"asetrate=44100*{pitch_factor},aresample=44100,{atempo_chain}"
        else:
            # Apenas altera o pitch sem ajustar velocidade
            filter_str = f"asetrate=44100*{pitch_factor},aresample=44100"
        
        cmd = [
            "ffmpeg", "-i", input_file,
            "-af", filter_str,
            "-y",  # Sobrescreve arquivo existente
            output_file
        ]
        
        try:
            result = subprocess.run(cmd, 
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception as e:
            print(f"✗ Erro ao ajustar pitch: {e}")
            return False
    
    def adjust_pitch_sox(self, input_file, output_file, semitones=0):
        """
        Ajusta o pitch usando SoX (mantém duração automaticamente)
        SoX é mais preciso que FFmpeg para ajuste de pitch
        
        Args:
            input_file: Arquivo de entrada
            output_file: Arquivo de saída
            semitones: Número de semitons (+/- 12 = 1 oitava)
                       +3 a +5 = voz feminina
                       +5 a +7 = voz infantil
        """
        if not self.has_sox:
            print("⚠️  SoX não encontrado. Instale com: brew install sox")
            return False
        
        cmd = [
            "sox", input_file, output_file,
            "pitch", str(int(semitones * 100)), # SoX usa cents (100 cents = 1 semitom)
            "rate", "16000"  
        ]
        
        try:
            result = subprocess.run(cmd,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception as e:
            print(f"✗ Erro ao ajustar pitch com SoX: {e}")
            return False
    
    def synthesize_with_pitch(self, text, output_file="output.wav", pitch_semitones=0, length_scale=1.0, noise_scale=0.6, noise_w=0.8, play=False):
        """
        Sintetiza texto e ajusta o pitch
        
        Args:
            text: Texto para sintetizar
            output_file: Arquivo final
            pitch_semitones: Ajuste em semitons (preferencial se usar SoX)
                            +3 a +5 = feminino, +5 a +7 = infantil
            length_scale, noise_scale, noise_w: Parâmetros do Piper
            play: Se True, reproduz automaticamente
            use_sox: Force usar SoX (True) ou FFmpeg (False), None = auto
        """
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_file = tmp.name
            
        try:
            # Gera áudio com Piper
            print(f"🎙️ Gerando áudio...")
            inicio = time.time()
            if not self.synthesize(text, temp_file, length_scale, noise_scale, noise_w):
                return False
            print("Tempo de geração audio: " + str(time.time() - inicio))

            inicio = time.time()

            # Ajusta pitch
            if pitch_semitones != 0:
                print(f"🎵 Ajustando pitch com SoX ({pitch_semitones:+d} semitons)...")
                if not self.adjust_pitch_sox(temp_file, output_file, pitch_semitones):
                    return False
            else:
                # Sem ajuste de pitch, apenas copia
                import shutil
                shutil.copy(temp_file, output_file)
            
            print("Tempo de afinação da voz: " + str(time.time() - inicio))

            print(f"✓ Áudio finalizado: {output_file}")
            
            # Reproduz se solicitado
            if play:
                subprocess.run(["afplay", output_file])
            
            return True
        
        finally:
            # Remove arquivo temporário
            if os.path.exists(temp_file):
                os.remove(temp_file)
