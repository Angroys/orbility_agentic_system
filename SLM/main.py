from huggingface_hub import login
from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from dataclasses import dataclass


# Config for all SLM parameters
@dataclass
class SLMConfig:
    token: str
    model_id: str
    return_tensors: str
    max_new_tokens: int
    temperature: float
    skip_special_tokens: bool


# Main Model
class SLM:
    def __init__(
        self,
        config: SLMConfig,
    ):
        self.__config = config
        self.__auth(token=self.__config.token)

        self.__tokenizer, self.__model = self.__create_model(
            model_id=self.__config.model_id
        )

    # Auth in haggingface
    @staticmethod
    def __auth(
        token,
    ):
        login(token=token)

    # Create tokenizer and model
    @staticmethod
    def __create_model(
        model_id: str,
    ):
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        ).eval()

        return tokenizer, model

    def __preparation_prompt(
        self,
        msg: list[list[dict]],
    ):
        inputs = self.__tokenizer.apply_chat_template(
            msg,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors=self.__config.return_tensors,
        ).to(self.__model.device)

        return inputs

    def __decode(
        self,
        outputs,
        skip_special_tokens: bool,
    ):
        return self.__tokenizer.decode(
            outputs[0], skip_special_tokens=skip_special_tokens
        )

    def input(
        self,
        prompt: list[list[dict]],
    ):
        prompt[0][1]["content"][0]["text"] = (
            prompt[0][1]["content"][0]["text"] + "<@<FINISHED&SYSTEM&USER&PROMPT>@>"
        )

        with torch.inference_mode():
            outputs = self.__model.generate(
                **(self.__preparation_prompt(msg=prompt)),
                max_new_tokens=self.__config.max_new_tokens
            )

        response = self.__decode(outputs=outputs, skip_special_tokens=True)

        return response.split("<@<FINISHED&SYSTEM&USER&PROMPT>@>\nmodel\n")[-1]


# Simple example
if __name__ == "__main__":
    # Init configuration
    config = SLMConfig(
        token="",
        model_id="google/gemma-3-1B-it",
        return_tensors="pt",
        max_new_tokens=500,
        temperature=0.8,
        skip_special_tokens=True,
    )

    slm = SLM(
        config=config,
    )  # Create model

    # --------------------------------------------------------

    # Example prompt
    prompt = [
        [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": """
            You are an AI assistant that answers any question the user asks.
            """,
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": "What is your name?"}],
            },
        ],
    ]
    slm.input(prompt=prompt)
