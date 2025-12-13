import shutil
import os

import numpy as np
from pydub import AudioSegment
from transformers import AutoProcessor, MusicgenForConditionalGeneration

import src.config
 
class MusicGenerator():
    """Music generator class"""
    def __init__(self):
        model = src.config.MUSIC_MODEL
        model_name = model.split("/")[-1]
        save_path = os.path.join(src.config.MODELS_DIR, model_name)
        
        # Checking if there enough space for the model
        model_size = self._get_model_size(model)
        
        if not os.path.isdir(save_path):
            _, _, free_space = shutil.disk_usage(src.config.MODELS_DIR)
            
            if model_size >= free_space:
                raise MemoryError(f"No left space for music model.\nRequired space: {model_size / (1024 ** 3):.1f} GB\nFree space: {free_space / (1024 ** 3):.1f} GB")
        
        self.processor = AutoProcessor.from_pretrained(model, cache_dir=save_path, use_safetensors=True, ignore_patterns=["*.bin"])
        self.model = MusicgenForConditionalGeneration.from_pretrained(model, cache_dir=save_path, use_safetensors=True)
        self.sr = self.model.config.audio_encoder.sampling_rate
    def _process_inspiration(self, path: str, target_sec: int | float):
        """Convert audio into convenient format"""
        audio = AudioSegment.from_file(path)
        audio = audio.set_frame_rate(self.sr).set_channels(1)
        
        arr = np.array(audio.get_array_of_samples())
        arr = arr.astype(np.float32) / (1 << (8 * audio.sample_width - 1))
        
        samples_count = int(target_sec * self.sr)
        return arr[:samples_count]

    def _get_model_size(self, model: str) -> float:
        if model == "facebook/musicgen-large":
            return (13.7 * (1024 ** 3)) * 1.3
        elif model == "facebook/musicgen-medium":
            return (8 * (1024 ** 3)) * 1.3
        elif model == "facebook/musicgen-small":
            return (2.4 * (1024 ** 3)) * 1.3
        else:
            raise ValueError

    def generate(self, prompt: str, length: int | float, inspiration_song_path: str, beginning_sec: int | float) -> tuple:
        """Generating music wave based on prompt"""
        full_wave = None
        tail_sec = 10
        tail_samples = int(tail_sec * self.sr)
        tail = None
        if inspiration_song_path:
            beginning = self._process_inspiration(inspiration_song_path, beginning_sec)
        else:
            beginning = None

        for _ in range(0, int(length/10)):
            if tail is not None:
                inputs = self.processor(
                    text=[prompt],
                    audio=tail,
                    sampling_rate=self.sr,
                    padding=True,
                    return_tensors="pt",
                )
            elif inspiration_song_path and beginning is not None:
                inputs = self.processor(
                    text=[prompt],
                    audio=beginning,
                    sampling_rate=self.sr,
                    padding=True,
                    return_tensors="pt",
                )
            else:
                inputs = self.processor(
                    text=[prompt],
                    padding=True,
                    return_tensors="pt",
                )

            audio_values = self.model.generate(
                **inputs,
                do_sample=True,
                guidance_scale=3,
                max_new_tokens=512,
            )

            wave = audio_values[0, 0].cpu().numpy()

            if inspiration_song_path and full_wave is None and beginning is not None:
                full_wave = wave[len(beginning):]
            elif full_wave is None:
                full_wave = wave
            else:
                new_part = wave[tail_samples:]
                full_wave = np.concatenate([full_wave, new_part])

            # the tail for next iteration
            tail = wave[-tail_samples:]
        
        return (self.sr, full_wave)
