import shutil
import os

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

import src.config

class TextGenerator():
    """Text generator class"""
    def __init__(self):
        model = src.config.TEXT_MODEL
        model_name = model.split("/")[-1]
        save_path = os.path.join(src.config.MODELS_DIR, model_name)
        
        # Checking if there enough space for the model
        model_size = self._get_model_size()
        
        if not os.path.isdir(save_path):
            _, _, free_space = shutil.disk_usage(src.config.MODELS_DIR)
    
            if model_size >= free_space:
                raise MemoryError(f"No left space for text model.\nRequired space: {model_size / (1024 ** 3):.1f} GB\nFree space: {free_space / (1024 ** 3):.1f} GB")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model, cache_dir=save_path, use_safetensors=True, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(model, cache_dir=save_path, device_map="cpu", dtype=torch.float32, use_safetensors=True, trust_remote_code=True)
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generating text based on prompt"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        text_input = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False
        )
        
        inputs = self.tokenizer([text_input], return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.6,
                top_p=0.9,
                repetition_penalty=1.05,
                do_sample=True
            )
        
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        return self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    def _get_model_size(self) -> float:
        return (4.1 * (1024 ** 3)) * 1.3