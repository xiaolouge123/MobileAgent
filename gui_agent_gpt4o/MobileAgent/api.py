import os
import json
import requests
import base64
import time
import mimetypes
import re
from PIL import Image
from loguru import logger
from MobileAgent.prompts import tools


openai_api_key = os.environ.get("OPENAI_API")
azure_api_key = os.environ.get("AZURE_API")
use_azure = bool(int(os.environ.get("USE_AZURE", 0)))


# img_path: local image path or image url like http://xxx
def process_one_img(img_path, host="127.0.0.1", port="8085", query="图中有什么"):
    url = f"http://{host}:{port}/generate/"
    headers = {"Content-Type": "application/json"}
    if img_path.startswith("http"):
        img_dct = {"type": "url", "data": img_path}
    else:
        with open(img_path, "rb") as fin:
            b64 = base64.b64encode(fin.read()).decode("utf-8")
        img_dct = {"type": "base64", "data": b64}
    llm_str = "<|im_start|>system\nYou are an AI assistant whose name is SenseChat-Vision(日日新多模态).<|im_end|><|im_start|>user\n<img></img>\n>{}<|im_end|>\n<|im_start|>assistant\n".format(
        query
    )
    data = {
        "inputs": llm_str,
        "parameters": {
            "do_sample": True,
            "ignore_eos": False,
            "max_new_tokens": 256,
            "stop_sequences": ["<|im_end|>", "<|im_start|>"],
            "top_k": 40,
            "top_p": 0.8,
            "temperature": 1.0,
            "repetition_penalty": 1.0,
        },
        "multimodal_params": {"images": [img_dct]},
    }
    response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        generated_text = response.json()
        return generated_text
        # print(generated_text)
    else:
        raise Exception(f"[-] Error: {response.status_code} {response.text}")


def process_one_img_stream(img_path, host="127.0.0.1", port="8085", query="图中有什么"):
    url = f"http://{host}:{port}/generate_stream"
    headers = {"Content-Type": "application/json"}
    if img_path.startswith("http"):
        img_dct = {"type": "url", "data": img_path}
    else:
        with open(img_path, "rb") as fin:
            b64 = base64.b64encode(fin.read()).decode("utf-8")
        img_dct = {"type": "base64", "data": b64}
    llm_str = "<|im_start|>system\nYou are an AI assistant whose name is SenseChat-Vision(日日新多模态).<|im_end|><|im_start|>user\n<img></img>\n>{}<|im_end|>\n<|im_start|>assistant\n".format(
        query
    )
    data = {
        "inputs": llm_str,
        "parameters": {
            "do_sample": True,
            "ignore_eos": False,
            "max_new_tokens": 256,
            "stop_sequences": ["<|im_end|>", "<|im_start|>"],
            "top_k": 40,
            "top_p": 0.8,
            "temperature": 1.0,
            "repetition_penalty": 1.0,
        },
        "multimodal_params": {"images": [img_dct]},
    }
    with requests.post(
        url, headers=headers, data=json.dumps(data), verify=False, stream=True
    ) as response:
        try:
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    print("Received line:", decoded_line)
                    data = json.loads(decoded_line.lstrip("data:"))
                    if bool(data.get("finished", False)):
                        break
        except json.JSONDecodeError:
            print("Received non-JSON data or partial JSON:", decoded_line)
        except UnicodeDecodeError as e:
            print(f"Error decoding line: {e}")
        except Exception as e:
            print(f"Error: {e}")


# process_one_img(img_path="/root/xiaohongshu.jpeg", host='103.177.28.204', port='12343')
# process_one_img(img_path="/Users/zhangyuchen/Downloads/main_12_marked.png", host='103.177.28.204', port='12343')
# process_one_img_stream(img_path="/Users/zhangyuchen/Downloads/main_12_marked.png", host='103.177.28.204', port='12343')


def output_parser(generation, width, height):
    action_space = [
        "CLICK",
        "SCROLL_DOWN",
        "SCROLL_UP",
        "SCROLL_LEFT",
        "SCROLL_RIGHT",
        "TYPE",
        "TASK_COMPLETE",
        "TASK_IMPOSSIBLE",
        "PRESS_BACK",
        "PRESS_ENTER",
        "PRESS_HOME",
    ]
    pos_action = ["CLICK", "SCROLL_DOWN", "SCROLL_UP", "SCROLL_LEFT", "SCROLL_RIGHT"]

    res = generation.get("generated_text", [])
    if len(res) > 0:
        res = res[0].rstrip("<|im_end|>").strip()
    else:
        raise ValueError(f"No generation text. {generation}")

    if res == "Action: PRESS BACK.":
        res = "Action: PRESS_BACK."

    match = re.search(r"Action: (\w+)", res)
    if not match:
        raise ValueError(f"Found no action name in generation: {res}")
    actionName = match.group(1).strip()

    if actionName not in action_space:
        raise ValueError(
            f"Not a supported action name in current action_space: {actionName}, {generation}"
        )

    if actionName in pos_action:
        match = re.search(r"\[\[(.*?)\]\]", res)
        if not match:
            raise ValueError(f"Pos action {actionName} is not valid: {res}")

        actionInput = eval(match.group(1).strip())
        actionInput = [
            int(item * width / 1000) if i % 2 == 0 else int(item * height / 1000)
            for i, item in enumerate(actionInput)
        ]

    elif actionName == "TYPE":
        match = re.search(r"\[(.*?)\]", res)
        if not match:
            raise ValueError(f"Type action is not valid: {res}")
        actionInput = match.group(1).strip()
    else:
        actionInput = ""
    return {
        "actionName": actionName,
        "actionInput": actionInput,
    }


def model_chat(img_path, instruction="打开qq音乐", host="103.237.29.210", port="12343"):
    img = Image.open(img_path)
    w, h = img.size
    instruction = instruction
    query = f"请根据UI界面和Agent操作指令生成下一步动作。Agent操作指令：{instruction}\n直接输出动作。"
    gen = process_one_img(img_path=img_path, host=host, port=port, query=query)
    action = output_parser(gen, w, h)
    return action  # {'actionName': 'CLICK', 'actionInput': [714, 276]}


def get_response_with_tools(payload):
    if use_azure:
        response = query_azure(payload)
    else:
        response = query_openai(payload)
    logger.info(f"LLM response: {response}")
    response_message = response["choices"][0]["message"]
    tool_calls = response_message.get("tool_calls")
    logger.info(f"Response message: {response_message}")
    logger.info(f"Tool calls: {tool_calls}")
    return response_message, tool_calls


def encode_image(image_path: str):
    """Encodes an image to base64 and determines the correct MIME type."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        raise ValueError(f"Cannot determine MIME type for {image_path}")

    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded_string}"


def query_openai(payload):
    """Sends a request to the OpenAI API and prints the response."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}",
    }
    proxies = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        # proxies=proxies,
    )
    logger.info(f"OpenAI response: {response.text}")
    return response.json()


def query_azure(payload, model="gpt4o-0513", version="2024-02-01"):
    headers = {"Content-Type": "application/json", "api-key": f"{azure_api_key}"}
    proxies = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    }
    response = requests.post(
        f"https://gpt-st-westus3-1.openai.azure.com/openai/deployments/{model}/chat/completions?api-version={version}",
        headers=headers,
        json=payload,
        proxies=proxies,
    )
    logger.info(f"Azure response: {response.text}")
    return response.json()


def get_current_time():
    current_time = time.localtime()
    formatted_time = time.strftime("%Y/%m/%d %H:%M:%S", current_time)
    return formatted_time


def generate_image_message(state: str, image_path: str) -> dict:
    base64_image = encode_image(image_path)
    image_request = {
        "role": "user",
        "content": [
            {"type": "text", "text": f"此截图时间：{get_current_time()}"},
            {"type": "text", "text": f"{state}"},
            {
                "type": "image_url",
                "image_url": {
                    "url": base64_image,
                    "detail": "high",
                },
            },
        ],
    }
    _image_request = {
        "role": "user",
        "content": [
            {"type": "text", "text": f"此截图时间：{get_current_time()}"},
            {"type": "text", "text": f"{state}"},
            {"type": "text", "text": "之前的屏幕截图，为节省空间已被删除。"},
        ],
    }
    return image_request, _image_request


def dummy_generate_image_message(state: str, image_path: str) -> dict:
    image_request = {
        "role": "user",
        "content": [
            {"type": "text", "text": f"此截图时间：{get_current_time()}"},
            {"type": "text", "text": f"{state}"},
            {
                "type": "image_url",
                "image_url": {
                    "url": image_path,
                    "detail": "high",
                },
            },
        ],
    }
    return image_request


def create_payload(
    system_prompt,
    user_instruction,
    history,
    img_cur,
    img_before_ops=None,
    img_after_ops=None,
    tools=None,
    max_tokens=3000,
    model="gpt-4o-2024-05-13",
):
    """
    interleave: [{"img_path": None, "text": None}]
    """
    messages = []
    _history = []
    _tmp = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
        _tmp.append({"role": "system", "content": system_prompt})
    if user_instruction:
        messages.append(
            {"role": "user", "content": [{"type": "text", "text": user_instruction}]}
        )
        _tmp.append(
            {"role": "user", "content": [{"type": "text", "text": user_instruction}]}
        )
    if len(history) > 0:
        messages.extend(history)
        _tmp.extend(history)
        _history.extend(history)

    if img_before_ops:
        msg, msg_wo_enc = generate_image_message(
            "这是上一个操作执行前的屏幕截图，若涉及到具体元素会用红色边框标出",
            img_before_ops,
        )
        messages.append(msg)
        _history.append(msg_wo_enc)
        _tmp.append(
            dummy_generate_image_message(
                "这是上一个操作执行前的屏幕截图，若涉及到具体元素会用红色边框标出",
                img_before_ops,
            )
        )

    if img_after_ops:
        msg, msg_wo_enc = generate_image_message(
            "这是上一个操作执行后的屏幕截图，表示操作的效果", img_after_ops
        )
        messages.append(msg)
        _history.append(msg_wo_enc)
        _tmp.append(
            dummy_generate_image_message(
                "这是上一个操作执行后的屏幕截图，表示操作的效果",
                img_after_ops,
            )
        )

    if img_cur:
        msg, msg_wo_enc = generate_image_message(
            "这是当前屏幕的截图(最新的屏幕截图)", img_cur
        )
        messages.append(msg)
        _history.append(msg_wo_enc)
        _tmp.append(
            dummy_generate_image_message(
                "这是当前屏幕的截图(最新的屏幕截图)",
                img_cur,
            )
        )
    if tools:
        p = {
            "model": model,
            "messages": _tmp,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": "auto",
            "response_format": {"type": "json_object"},
        }
        logger.info(f"Request payload: {json.dumps(p, ensure_ascii=False)}")
    else:
        p = {
            "model": model,
            "messages": _tmp,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        logger.info(f"Request payload: {json.dumps(p, ensure_ascii=False)}")

    if tools:
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": "auto",
            "response_format": {"type": "json_object"},
        }, _history
    else:
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }, _history


def request_with_tools(
    system_prompt,
    user_instruction,
    history,
    img_cur,
    img_before_ops=None,
    img_after_ops=None,
    enable_tools=True,
) -> dict:
    # include build message'
    if enable_tools:
        payload, _history = create_payload(
            system_prompt,
            user_instruction,
            history,
            img_cur,
            img_before_ops,
            img_after_ops,
            tools,
        )
    else:
        payload, _history = create_payload(
            system_prompt,
            user_instruction,
            history,
            img_cur,
            img_before_ops,
            img_after_ops,
        )

    response_message, tools_calls = get_response_with_tools(payload)
    return response_message, tools_calls, _history
