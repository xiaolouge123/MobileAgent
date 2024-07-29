import json
import requests
import base64
import re
from PIL import Image
# img_path: local image path or image url like http://xxx
def process_one_img(img_path,host='127.0.0.1', port='8085', query='图中有什么'):
    url = f'http://{host}:{port}/generate/'
    headers = {
        'Content-Type': 'application/json'
    }
    if img_path.startswith("http"):
        img_dct = {"type": "url", "data": img_path}
    else:
        with open(img_path, 'rb') as fin:
            b64 = base64.b64encode(fin.read()).decode("utf-8")
        img_dct = {'type': "base64", "data": b64}
    llm_str = '<|im_start|>system\nYou are an AI assistant whose name is SenseChat-Vision(日日新多模态).<|im_end|><|im_start|>user\n<img></img>\n>{}<|im_end|>\n<|im_start|>assistant\n'.format(query)
    data = {
        'inputs': llm_str,
        'parameters': {
            "do_sample": True,
            "ignore_eos": False,
            "max_new_tokens": 256,
            "stop_sequences": ['<|im_end|>', '<|im_start|>'],
            "top_k": 40,
            "top_p": 0.8,
            "temperature": 1.0,
            "repetition_penalty": 1.0,
        },
        'multimodal_params': {
            'images': [img_dct]
        }
    }
    response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)
    if response.status_code == 200:
        generated_text = response.json()
        return generated_text
        # print(generated_text)
    else:
        raise Exception(f'[-] Error: {response.status_code} {response.text}')

def process_one_img_stream(img_path,host='127.0.0.1', port='8085', query='图中有什么'):
    url = f'http://{host}:{port}/generate_stream'
    headers = {
        'Content-Type': 'application/json'
    }
    if img_path.startswith("http"):
        img_dct = {"type": "url", "data": img_path}
    else:
        with open(img_path, 'rb') as fin:
            b64 = base64.b64encode(fin.read()).decode("utf-8")
        img_dct = {'type': "base64", "data": b64}
    llm_str = '<|im_start|>system\nYou are an AI assistant whose name is SenseChat-Vision(日日新多模态).<|im_end|><|im_start|>user\n<img></img>\n>{}<|im_end|>\n<|im_start|>assistant\n'.format(query)
    data = {
        'inputs': llm_str,
        'parameters': {
            "do_sample": True,
            "ignore_eos": False,
            "max_new_tokens": 256,
            "stop_sequences": ['<|im_end|>', '<|im_start|>'],
            "top_k": 40,
            "top_p": 0.8,
            "temperature": 1.0,
            "repetition_penalty": 1.0,
        },
        'multimodal_params': {
            'images': [img_dct]
        }
    }
    with requests.post(url, headers=headers, data=json.dumps(data), verify=False, stream=True) as response:
        try:
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    print("Received line:", decoded_line)
                    data = json.loads(decoded_line.lstrip('data:'))
                    if bool(data.get('finished', False)):
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
    action_space = ["CLICK", "SCROLL_DOWN", "SCROLL_UP", "SCROLL_LEFT", "SCROLL_RIGHT", "TYPE", "TASK_COMPLETE", "TASK_IMPOSSIBLE", "PRESS_BACK", "PRESS_ENTER", "PRESS_HOME"]
    pos_action = ["CLICK", "SCROLL_DOWN", "SCROLL_UP", "SCROLL_LEFT", "SCROLL_RIGHT"]

    res = generation.get('generated_text', [])
    if len(res)>0:
        res = res[0].rstrip('<|im_end|>').strip()
    else:
        raise ValueError(f'No generation text. {generation}')
    
    if res == 'Action: PRESS BACK.':
        res = 'Action: PRESS_BACK.'

    match = re.search(r"Action: (\w+)", res)
    if not match:
        raise ValueError(f"Found no action name in generation: {res}")
    actionName = match.group(1).strip()
    
    if actionName not in action_space:
        raise ValueError(f"Not a supported action name in current action_space: {actionName}, {generation}")
    
    if actionName in pos_action:
        match = re.search(r'\[\[(.*?)\]\]', res)
        if not match:
            raise ValueError(f"Pos action {actionName} is not valid: {res}")
        
        actionInput = eval(match.group(1).strip())
        actionInput = [int(item * width / 1000) if i % 2 == 0 else int(item * height / 1000) for i, item in enumerate(actionInput)]
    
    elif actionName == "TYPE":
        match = re.search(r'\[(.*?)\]', res)
        if not match:
            raise ValueError(f"Type action is not valid: {res}")
        actionInput = match.group(1).strip()
    else:
        actionInput = ''
    return {
        'actionName':actionName,
        'actionInput':actionInput,
    }

def model_chat(img_path, instruction='打开qq音乐', host='103.237.29.210', port='12343'):
    img = Image.open(img_path)
    w,h = img.size
    instruction = instruction
    query = f"请根据UI界面和Agent操作指令生成下一步动作。Agent操作指令：{instruction}\n直接输出动作。"
    gen = process_one_img(img_path=img_path, host=host, port=port, query=query)
    action = output_parser(gen, w, h)
    return action # {'actionName': 'CLICK', 'actionInput': [714, 276]}
