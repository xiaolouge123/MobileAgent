import os
import time
import json
import argparse
import shutil
from uuid import uuid4 as uuid
from loguru import logger
from MobileAgent.api import model_chat
from PIL import Image, ImageDraw, ImageFont
import math

from MobileAgent.controller import get_screenshot, tap, slide, type, back, home, enter

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

def main(args):
    uuid = get_id()
    logger.add(f"./screenshot/{uuid}.log", format="{time} {level} {message}", level="INFO")
    logger.info(f"Task init {uuid}")
    logger.info(f"Input args: {args}")
    
    #####
    adb_path = args.adb_path
    output_dir = args.output
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

    iter = 0
    while True:
        logger.info(f'Step tracing {iter}')
        screenshot_file = "./screenshot/screenshot.jpg"
        get_screenshot(adb_path)
        gen_action = model_chat(screenshot_file, args.task_instruction)
        copy_screenshot(screenshot_file, temp_file, iter)
        label_screenshot_and_save(screenshot_file, gen_action, labeled_screenshot_folder, iter)
        logger.info(f"Step tracing {iter} generated action : {gen_action}")

        if gen_action.get('actionName') == 'CLICK':
            try:
                coordinate = gen_action.get('actionInput')
                x, y = int(coordinate[0]), int(coordinate[1])
                tap(adb_path, x, y)
            except  Exception as e:
                raise ValueError(f"Step tracing {iter} wrong CLICK action input, {gen_action}")
            
        elif gen_action.get('actionName').startswith('SCROLL_'):
            try:
                coordinates = gen_action.get('actionInput')
                coordinate1 = coordinates[0], coordinates[1]
                coordinate2 = coordinates[2], coordinates[3]
                x1, y1 = int(coordinate1[0]), int(coordinate1[1])
                x2, y2 = int(coordinate2[0]), int(coordinate2[1])
                slide(adb_path, x1, y1, x2, y2)
            except  Exception as e:
                raise ValueError(f"Step tracing {iter} wrong SCROLL action input, {gen_action}")
        
        elif gen_action.get('actionName') == 'TYPE':
            text = gen_action.get('actionInput')
            type(adb_path, text)
        
        elif gen_action.get('actionName') == "PRESS_BACK":
            back(adb_path)
        
        elif gen_action.get('actionName') == "PRESS_HOME":
            home(adb_path)
        
        elif gen_action.get('actionName') == "PRESS_ENTER":
            enter(adb_path)

        elif gen_action.get('actionName') == "TASK_COMPLETE":
            logger.info(f"Step tracing {iter} decide TASK_COMPLETE \n generated action : {gen_action} \n closing the loop")
            break

        elif gen_action.get('actionName') == "TASK_IMPOSSIBLE":
            logger.info(f"Step tracing {iter} decide TASK_IMPOSSIBLE \n generated action : {gen_action} \n closing the loop")
            break
        iter += 1

        time.sleep(5)
    
    logger.info('Agent Looping is over, we ara about to close. copy log file to task folder')
    source_path = f"./screenshot/{uuid}.log"
    destination_path = os.path.join(temp_file, f"{uuid}.log")
    shutil.copy(source_path, destination_path)

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_instruction", type=str)
    parser.add_argument("--output", type=str, default='./output')
    parser.add_argument("--adb_path", default='/usr/local/bin/adb', type=str)
    args = parser.parse_args()
    main(args)
