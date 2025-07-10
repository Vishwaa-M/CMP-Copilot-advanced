# core/llm.py

import os
import logging
import time
from typing import List, Dict, Optional
import asyncio

from dotenv import load_dotenv
# This is the import from your working example
from mistralai import Mistral
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

# Load environment variables from the .env file
load_dotenv()

# Configure a dedicated logger for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Global LLM Client Singleton ---
llm_client: Optional['MistralLLMClient'] = None


class MistralLLMClient:
    """
    An enterprise-grade client for stable interaction with the Mistral API.
    This version uses the async methods that are confirmed to work in your environment.
    """
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("Mistral API key cannot be None or empty.")
        logger.info(f"Initializing MistralLLMClient for model: {model_name}")
        self.client = Mistral(api_key=api_key)
        self.model_name = model_name
        logger.info("Mistral client initialized successfully.")

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def invoke_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        json_mode: bool = False
    ) -> Optional[str]:
        """
        Invokes the asynchronous chat completion endpoint with retry logic.
        """
        logger.debug(f"Invoking async chat completion for model {self.model_name} with {len(messages)} messages.")
        start_time = time.time()

        try:
            if not messages:
                logger.warning("No valid messages to send.")
                return None

            response_format = {"type": "json_object"} if json_mode else None

            # Using the async API call from your working example
            response = await self.client.chat.complete_async(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )

            duration = time.time() - start_time
            usage_info = f"Usage: {getattr(response, 'usage', 'N/A')}"
            logger.info(f"Chat completion successful. Duration: {duration:.2f}s. {usage_info}")

            if response.choices and response.choices[0].message:
                return response.choices[0].message.content
            else:
                logger.warning("Received a response with no choices.")
                return None

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Chat completion failed after {duration:.2f}s. Error: {e}", exc_info=True)
            raise


def get_llm_client() -> 'MistralLLMClient':
    """
    Initializes and returns the singleton LLM client instance.
    """
    global llm_client
    if llm_client is None:
        logger.info("Creating a new singleton instance of the LLM client.")
        api_key = os.getenv("MISTRAL_API_KEY")
        model_name = os.getenv("MISTRAL_MODEL_NAME", "mistral-large-latest")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in .env file.")
        
        llm_client = MistralLLMClient(api_key=api_key, model_name=model_name)
    return llm_client

# --- Standalone Test Block ---
if __name__ == "__main__":
    async def main():
        print("--- Testing MistralLLMClient (Async Version) ---")
        try:
            client = get_llm_client()

            test_messages = [
                {"role": "user", "content": "What is the capital of France?"}
            ]

            response_content = await client.invoke_chat_completion(test_messages)

            if response_content:
                print("\n--- Standard Chat Response ---")
                print(response_content)
                print("----------------------------")
            else:
                print("Failed to get a standard response.")

        except Exception as e:
            print(f"\nAn error occurred during the test: {e}")

    # Run the async main function
    asyncio.run(main())
