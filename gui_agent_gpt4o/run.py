import os
import time
import json
import argparse
import shutil
from uuid import uuid4 as uuid
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
import math
from rich import print as color_print


from MobileAgent.api import model_chat, request_with_tools
from MobileAgent.prompts import get_prompt_with_tools, tools
from MobileAgent.controller import get_screenshot, home, ime_switch, handle_tool_calls


img_before_ops, img_after_ops = None, None

def get_id():
    return str(uuid()).replace('-', '')

def get_all_files_in_folder(folder_path):
    file_list = []
    for file_name in os.listdir(folder_path):
        file_list.append(file_name)
    return file_list

def copy_screenshot(src_img, target_dir, iter):
    destination_path = os.path.join(target_dir, f"screenshot_iter_{iter}.jpg")
    shutil.copy(src_img, destination_path)

def copy_ops_screenshot(src_img_before_ops, src_img_after_ops, target_dir, iter):
    destination_path = os.path.join(target_dir, f"before_ops_screenshot_iter_{iter}.jpg")
    shutil.copy(src_img_before_ops, destination_path)
    destination_path = os.path.join(target_dir, f"after_ops_screenshot_iter_{iter}.jpg")
    shutil.copy(src_img_after_ops, destination_path)

def draw_arrow(draw, start, end, arrow_length=10, arrow_angle=30, arrow_color="red"):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    angle = math.atan2(dy, dx)
    draw.line([start, end], fill=arrow_color, width=3)
    arrow_tip_x1 = end[0] - arrow_length * math.cos(angle + math.radians(arrow_angle))
    arrow_tip_y1 = end[1] - arrow_length * math.sin(angle + math.radians(arrow_angle))
    arrow_tip_x2 = end[0] - arrow_length * math.cos(angle - math.radians(arrow_angle))
    arrow_tip_y2 = end[1] - arrow_length * math.sin(angle - math.radians(arrow_angle))
    draw.line([end, (arrow_tip_x1, arrow_tip_y1)], fill=arrow_color, width=3)
    draw.line([end, (arrow_tip_x2, arrow_tip_y2)], fill=arrow_color, width=3)

def add_text_to_image(img, draw, text, position='bottom', font_path='/System/Library/Fonts/STHeiti Light.ttc', font_size=40, text_color='purple', border_size=100):
    """
    添加文字到图片的顶部或底部边缘区域。
    
    参数：
    img: image obj
    text: 要添加的文字。
    position: 文字位置，'top' 或 'bottom'。
    font_path: 字体文件路径。
    font_size: 字体大小。
    text_color: 文字颜色。
    border_size: 边框大小。
    """
    if position == 'top':
        new_image = Image.new("RGB", (img.width, img.height + border_size), "white")
        new_image.paste(img, (0, border_size))  # 将原图粘贴到底部，顶部留白
        text_position = (10, 10)
    else:
        new_image = Image.new("RGB", (img.width, img.height + border_size), "white")
        new_image.paste(img, (0, 0))  # 将原图粘贴到顶部
        text_position = (10, img.height + 10)
    draw = ImageDraw.Draw(new_image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        logger.warning('font error')
        font = ImageFont.load_default()
    draw.text(text_position, text, font=font, fill=text_color)
    return new_image

def label_screenshot_and_save(src_img, gen_action, target_dir, iter):
    img = Image.open(src_img)
    draw = ImageDraw.Draw(img)
    width, height = img.size
    action_name = gen_action.get('actionName')
    action_input = gen_action.get('actionInput')
    if action_name == 'CLICK':
        radia = 40
        x, y = int(action_input[0]), int(action_input[1])
        draw.ellipse((x-radia, y-radia, x+radia, y+radia), fill='gold')
    elif action_name.startswith('SCROLL_'):
        coordinate1 = action_input[0], action_input[1]
        coordinate2 = action_input[2], action_input[3]
        x1, y1 = int(coordinate1[0]), int(coordinate1[1])
        x2, y2 = int(coordinate2[0]), int(coordinate2[1])
        draw_arrow(draw, (x1, y1), (x2, y2))
    
    text = f"Step {iter}"
    text += f'\n{gen_action}'
    img = add_text_to_image(img, draw, text)
    
    img.save(os.path.join(target_dir, f"screenshot_iter_{iter}.jpg"))

def get_previous_ops_img_paths():
    return img_before_ops, img_after_ops

def set_ops_img_paths(before_path, after_path):
    global img_before_ops, img_after_ops
    img_before_ops = before_path
    img_after_ops = after_path

def ask_question(question):
    color_print(f"[yellow]{question}[/yellow]")
    user_input = input("User >>>")
    return user_input

def main(args):
    uuid = get_id()
    logger.add(f"./screenshot/{uuid}.log", format="{time} {level} {message}", level="INFO")
    logger.info(f"Task init {uuid}")
    logger.info(f"Input args: {args}")
    
    #####
    adb_path = args.adb_path
    output_dir = args.output
    max_task_step = 30
    #####
    
    if args.output is not None:
        os.makedirs(output_dir, exist_ok=True)
    temp_file = os.path.join(output_dir, uuid)
    labeled_screenshot_folder = os.path.join(output_dir, uuid, 'labeled')
    
    screenshot = "screenshot"
    if not os.path.exists(temp_file):
        os.mkdir(temp_file)
    if not os.path.exists(screenshot):
        os.mkdir(screenshot)
    if not os.path.exists(labeled_screenshot_folder):
        os.mkdir(labeled_screenshot_folder)

    with open(os.path.join(temp_file, 'meta_info.json'), 'w') as fw:
        fw.write(json.dumps(args.__dict__, ensure_ascii=False))

    logger.info(F"Task Start: {args.task_instruction}")
    system_prompt, user_instruction = get_prompt_with_tools(args.task_instruction)
    history = []

    iter = 0
    while True:
        logger.info(f'Step tracing {iter}')
        screenshot_file = "./screenshot/screenshot.jpg"
        get_screenshot(adb_path)
        copy_screenshot(screenshot_file, temp_file, iter)
        current_screenshot_path = os.path.join(temp_file, f"screenshot_iter_{iter}.jpg")
        
        img_before_ops, img_after_ops = get_previous_ops_img_paths()
        if img_before_ops and img_after_ops:
            copy_ops_screenshot(img_before_ops, img_after_ops, temp_file, iter)

        response_message, tools_calls, _history = request_with_tools(system_prompt, user_instruction, history, img_cur=current_screenshot_path, img_before_ops=img_before_ops, img_after_ops=img_after_ops,  enable_tools=True)
        history = _history
        history.append(response_message)

        model_output = {
            "assistant":"",
            "asking_user_for_help":{
                "require_help": "0",
                "request_detail":""
            },
            "finish":"0",
        }
        if response_message['content']:
            model_output = json.loads(response_message['content'])
            response_content = model_output.get('assistant')
            color_print(f"[yellow]{response_content}[/yellow]")
        
        if tools_calls:
            function_response, img_before, img_after = handle_tool_calls(tools_calls, adb_path)
            history.append(function_response)
            set_ops_img_paths(img_before, img_after)
        
        if bool(int(model_output.get('finish'))):
            color_print(f"[green]任务已完成啦！[/green]")
        
        iter += 1
        if iter > max_task_step:
            color_print(f"[red]超过最大步骤数目[/red]")
            logger.warning(f"Task action step exceed {max_task_step}, force quit.")
            break
            
        asking_user_for_help = model_output.get('asking_user_for_help')
        if bool(int(asking_user_for_help['require_help'])):
            user_input = ask_question(asking_user_for_help['request_detail'])
            if user_input != '':
                history.append({
                    "role":"user",
                    "content":[{"type": "text", "text": user_input}]
                })
            asking_user_for_help = "0"

        time.sleep(2)
    
    logger.info('Agent Looping is over, we ara about to close. copy log file to task folder')
    source_path = f"./screenshot/{uuid}.log"
    destination_path = os.path.join(temp_file, f"{uuid}.log")
    shutil.copy(source_path, destination_path)
    home(adb_path)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_instruction", type=str)
    parser.add_argument("--output", type=str, default='./output')
    parser.add_argument("--adb_path", default='/usr/local/bin/adb', type=str)
    args = parser.parse_args()
    main(args)
