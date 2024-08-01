import os
import time
import json
import re
import subprocess

# import uiautomator2 as u2
import requests
from PIL import Image, ImageDraw
from loguru import logger

# d = u2.connect()
delay = 2
use_u2 = False


def get_size(adb_path):
    command = adb_path + " shell wm size"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    resolution_line = result.stdout.strip().split("\n")[-1]
    width, height = map(int, resolution_line.split(" ")[-1].split("x"))
    return width, height


def get_xml(adb_path):
    process = subprocess.Popen(
        [adb_path, "shell", "uiautomator", "dump"], stdout=subprocess.PIPE
    )
    process.communicate()
    subprocess.run(
        [adb_path, "pull", "/sdcard/window_dump.xml", "./xml/window_dump.xml"]
    )


def take_screenshots(
    adb_path,
    num_screenshots,
    output_folder,
    crop_y_start,
    crop_y_end,
    slide_y_start,
    slide_y_end,
):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for i in range(num_screenshots):
        command = adb_path + f" shell rm /sdcard/screenshot{i}.png"
        subprocess.run(command, capture_output=True, text=True, shell=True)
        command = adb_path + f" shell screencap -p /sdcard/screenshot{i}.png"
        subprocess.run(command, capture_output=True, text=True, shell=True)
        command = adb_path + f" pull /sdcard/screenshot{i}.png {output_folder}"
        subprocess.run(command, capture_output=True, text=True, shell=True)
        image = Image.open(f"{output_folder}/screenshot{i}.png")
        cropped_image = image.crop((0, crop_y_start, image.width, crop_y_end))
        cropped_image.save(f"{output_folder}/screenshot{i}.png")
        subprocess.run(
            [
                adb_path,
                "shell",
                "input",
                "swipe",
                "500",
                str(slide_y_start),
                "500",
                str(slide_y_end),
            ]
        )


def get_screenshot(adb_path, save_path=None):
    command = adb_path + " shell rm /sdcard/screenshot.png"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)
    command = adb_path + " shell screencap -p /sdcard/screenshot.png"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)
    command = adb_path + " pull /sdcard/screenshot.png ./screenshot"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    image_path = "./screenshot/screenshot.png"
    if save_path is None:
        save_path = "./screenshot/screenshot.jpg"
    image = Image.open(image_path)
    image.convert("RGB").save(save_path, "JPEG")
    os.remove(image_path)


def get_keyboard(adb_path):
    command = adb_path + " shell dumpsys input_method"
    process = subprocess.run(
        command, capture_output=True, text=True, shell=True, encoding="utf-8"
    )
    output = process.stdout.strip()
    for line in output.split("\n"):
        if "mInputShown" in line:
            if "mInputShown=true" in line:

                for line in output.split("\n"):
                    if "hintText" in line:
                        hintText = line.split("hintText=")[-1].split(" label")[0]
                        break

                return True, hintText
            elif "mInputShown=false" in line:
                return False, None


def tap(adb_path, x, y):
    if use_u2:
        d.click(x, y)
    else:
        command = adb_path + f" shell input tap {x} {y}"
        subprocess.run(command, capture_output=True, text=True, shell=True)


def contains_cjk(text):
    # 使用Unicode范围来匹配CJK字符
    cjk_pattern = re.compile(
        r"[\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]"
    )
    return bool(cjk_pattern.search(text))


def ime_switch(adb_path, ime="adb"):
    if ime == "adb":
        command = adb_path + f" shell ime set com.android.adbkeyboard/.AdbIME"
        subprocess.run(command, capture_output=True, text=True, shell=True)
    else:
        command = (
            adb_path
            + f" shell ime set com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"
        )
        subprocess.run(command, capture_output=True, text=True, shell=True)


def type(adb_path, text):
    text = text.replace("\\n", "_").replace("\n", "_")
    if contains_cjk(text):
        ime_switch(adb_path, ime="adb")
        time.sleep(1)
        command = adb_path + f' shell am broadcast -a ADB_INPUT_TEXT --es msg "{text}"'
        subprocess.run(command, capture_output=True, text=True, shell=True)
        time.sleep(1)
        ime_switch(adb_path, ime=None)
        return

    for char in text:
        if char == " ":
            command = adb_path + f" shell input text %s"
            subprocess.run(command, capture_output=True, text=True, shell=True)
        elif char == "_":
            command = adb_path + f" shell input keyevent 66"
            subprocess.run(command, capture_output=True, text=True, shell=True)
        elif "a" <= char <= "z" or "A" <= char <= "Z" or char.isdigit():
            command = adb_path + f" shell input text {char}"
            subprocess.run(command, capture_output=True, text=True, shell=True)
        elif char in "-.,!?@'°/:;()":
            command = adb_path + f' shell input text "{char}"'
            subprocess.run(command, capture_output=True, text=True, shell=True)
        else:
            ime_switch(adb_path, ime="adb")
            time.sleep(0.1)
            command = (
                adb_path + f' shell am broadcast -a ADB_INPUT_TEXT --es msg "{char}"'
            )
            subprocess.run(command, capture_output=True, text=True, shell=True)
            time.sleep(1)
            ime_switch(adb_path, ime=None)


def enter(adb_path):
    command = adb_path + f" shell input keyevent 66"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def slide(adb_path, x1, y1, x2, y2):
    command = adb_path + f" shell input swipe {x1} {y1} {x2} {y2} 500"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def swipe(adb_path, direction, distance=500, duration=500):
    # 获取屏幕尺寸
    size_command = f"{adb_path} shell wm size"
    result = subprocess.run(size_command, capture_output=True, text=True, shell=True)
    width, height = map(int, result.stdout.split()[-1].split("x"))
    # 计算中心点
    center_x, center_y = width // 2, height // 2
    # 根据方向计算起始点和终点
    if direction.lower() == "up":
        x1, y1 = center_x, center_y + distance // 2
        x2, y2 = center_x, center_y - distance // 2
    elif direction.lower() == "down":
        x1, y1 = center_x, center_y - distance // 2
        x2, y2 = center_x, center_y + distance // 2
    elif direction.lower() == "left":
        x1, y1 = center_x + distance // 2, center_y
        x2, y2 = center_x - distance // 2, center_y
    elif direction.lower() == "right":
        x1, y1 = center_x - distance // 2, center_y
        x2, y2 = center_x + distance // 2, center_y
    else:
        raise ValueError("Invalid direction. Use 'up', 'down', 'left', or 'right'.")
    # 执行滑动命令
    command = f"{adb_path} shell input swipe {x1} {y1} {x2} {y2} {duration}"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def longpress(adb_path, x, y, duration=1000):
    command = f"{adb_path} shell input swipe {x} {y} {x} {y} {duration}"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def back(adb_path):
    command = adb_path + f" shell input keyevent 4"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def home(adb_path):
    command = (
        adb_path
        + f" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME"
    )
    subprocess.run(command, capture_output=True, text=True, shell=True)


def extract_coordinates(input_string, width, height):
    # 使用正则表达式找到所有的整数
    numbers = re.findall(r"\d+", input_string)
    # 将找到的数字转换为整数类型
    numbers = list(map(int, numbers))[-4:]
    # 判断是否找到了足够的坐标数
    if len(numbers) == 4:
        left, top, right, bottom = numbers
        left = int(width * left / 1000)
        top = int(height * top / 1000)
        right = int(width * right / 1000)
        bottom = int(height * bottom / 1000)
        return [left, top, right, bottom]
    else:
        # 如果没有找到四个数字，返回错误信息或者None
        raise ValueError


def gui_model_api(api_path, image_path, question):
    logger.info(f"Calling GUI model API on {question}")
    headers = {"Connection": "close"}
    with open(image_path, "rb") as img:
        files = {"image": img}
        data = {
            "modal_type": "image",
            "image_path": "not use",
            "useocr": "no",
            "question": question,
            "restart": "yes",
        }
        response = requests.post(url=api_path, headers=headers, files=files, data=data)
    if response.status_code != 200:
        raise ConnectionError(
            "POST {} failed with status code {}".format(api_path, response.status_code)
        )
    pred = response.json()
    logger.info(f"GUI Model API response: {pred}")
    return pred["answer"]


def grounding(element_description: str, image_before_operation: str) -> list:
    api_path = "http://101.230.144.192:10067/gui_v3.7/service"
    prompt = f"确定并框出界面中<ref>{element_description}</ref>图标的精确位置。"
    image = Image.open(image_before_operation)
    res = gui_model_api(api_path, image_before_operation, prompt)
    boundingbox = extract_coordinates(res, image.width, image.height)
    logger.info(f"Bounding box: {boundingbox}")

    draw = ImageDraw.Draw(image)
    if boundingbox:
        # 绘制边框，这里我们使用红色边框，宽度为 5 像素
        draw.rectangle(boundingbox, outline="red", width=5)
        image.save(image_before_operation)

    return boundingbox, image_before_operation


def control_handler(tool_call, adb_path):
    logger.info(f"Handling control tool call: {tool_call}")
    img_before_ops_path = f"./screenshot/screenshot_before_ops.png"
    get_screenshot(adb_path, save_path=img_before_ops_path)
    arguments = json.loads(tool_call["function"]["arguments"])
    operation = arguments.get("operation")
    ops_detail = []
    if operation == "tap":
        logger.info("Handling tap operation...")
        ui_query = arguments.get("elements")
        bbox, img_before_ops_path = grounding(ui_query, img_before_ops_path)
        x = (bbox[0] + bbox[2]) / 2
        y = (bbox[1] + bbox[3]) / 2
        logger.info(f"Tap coordinates: ({x}, {y})")
        tap(adb_path, x, y)
        function_response = (
            f"对{ui_query}元素的点击操作已下发至设备，具体效果以屏幕截图为准。"
        )
        ops_detail.append(
            {
                "ops": "CLICK",
                "param": (x, y),
                "name": "tap",
                "type": "controller",
                "bbox": bbox,
                "ui_query": ui_query,
            }
        )
    elif operation == "text":
        # tap input ui area
        ui_query = arguments.get("elements")
        if ui_query:
            bbox, img_before_ops_path = grounding(ui_query, img_before_ops_path)
            x = (bbox[0] + bbox[2]) / 2
            y = (bbox[1] + bbox[3]) / 2
            tap(adb_path, x, y)
            ops_detail.append(
                {
                    "ops": "CLICK",
                    "param": (x, y),
                    "name": "text",
                    "type": "controller",
                    "bbox": bbox,
                    "ui_query": ui_query,
                }
            )
        # input text content
        text_content = arguments.get("text_content")
        type(adb_path, text_content)
        ops_detail.append(
            {"ops": "TYPE", "param": text_content, "name": "text", "type": "controller"}
        )
        # press enter
        time.sleep(delay)
        enter(adb_path)
        ops_detail.append(
            {"ops": "ENTER", "param": None, "name": "text", "type": "controller"}
        )
        function_response = f"输入{text_content}已下发至设备，具体效果以屏幕截图为准。"
    elif operation == "swipe":
        ui_query = arguments.get("elements")
        bbox, img_before_ops_path = grounding(ui_query, img_before_ops_path)
        direction = arguments.get("direction")
        swipe(adb_path, direction)
        ops_detail.append(
            {
                "ops": "SWIPE",
                "param": direction,
                "name": "swipe",
                "type": "controller",
                "bbox": bbox,
                "ui_query": ui_query,
            }
        )
        function_response = (
            f"{direction}方向的滑动操作已下发至设备，具体效果以屏幕截图为准。"
        )
    elif operation == "longclick":
        ui_query = arguments.get("elements")
        bbox, img_before_ops_path = grounding(ui_query, img_before_ops_path)
        x = (bbox[0] + bbox[2]) / 2
        y = (bbox[1] + bbox[3]) / 2
        longpress(adb_path, x, y)
        ops_detail.append(
            {
                "ops": "LONGPRESS",
                "param": (x, y),
                "name": "longclick",
                "type": "controller",
                "bbox": bbox,
                "ui_query": ui_query,
            }
        )
        function_response = (
            f"对{ui_query}元素的长按操作已下发至设备，具体效果以屏幕截图为准。"
        )
    elif operation == "back":
        b_times = arguments.get("back_times")
        for _ in range(int(b_times)):
            back(adb_path)
            time.sleep(0.5)
        ops_detail.append(
            {"ops": "BACK", "param": b_times, "name": "back", "type": "controller"}
        )
        function_response = "返回操作已下发至设备，具体效果以屏幕截图为准"
    elif operation == "home":
        home(adb_path)
        ops_detail.append(
            {"ops": "HOME", "param": None, "name": "back", "type": "controller"}
        )
        function_response = "回到桌面操作已下发至设备，具体效果以屏幕截图为准"
    else:
        return (
            {
                "tool_call_id": tool_call["id"],
                "role": "tool",
                "name": tool_call["function"]["name"],
                "content": f"{tool_call['function']['name']}没有被识别，请确保operation为\"tap\",\"swipe\",\"longclick\",\"text\",\"back\",\"home\"之一。",
            },
            img_before_ops_path,
            None,
            [],
        )

    controller_response = {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "name": tool_call["function"]["name"],
        "content": function_response,
    }
    # 操作后等待屏幕刷新
    time.sleep(delay)
    img_after_ops_path = f"./screenshot/screenshot_after_ops.png"
    get_screenshot(adb_path, save_path=img_after_ops_path)
    return controller_response, img_before_ops_path, img_after_ops_path, ops_detail


def shortcut_handler(tool_call, adb_path):
    logger.info(f"Handling shortcut tool call: {tool_call}")
    img_before_ops_path = f"./screenshot/screenshot_before_ops.png"
    get_screenshot(adb_path, save_path=img_before_ops_path)
    arguments = json.loads(tool_call["function"]["arguments"])
    ops_detail = []
    if arguments.get("shortcut_name") == "系统下拉菜单":
        # 为了快速实现写死了，最好是匹配设备后执行动作缓存
        # TODO 尝试理解后调整
        slide(adb_path, 650, 0, 650, 1100)
        time.sleep(0.5)
        slide(adb_path, 650, 0, 650, 1100)
        ops_detail.append(
            {
                "ops": "SLIDE",
                "param": (650, 0, 650, 1100),
                "name": "系统下拉菜单",
                "type": "shortcut_name",
            }
        )
    if arguments.get("shortcut_name") == "进入系统应用列表":
        home(adb_path)
        slide(adb_path, 360, 1000, 360, 0)
        ops_detail.append(
            {
                "ops": "SLIDE",
                "param": (360, 1000, 360, 0),
                "name": "进入系统应用列表",
                "type": "shortcut_name",
            }
        )
    time.sleep(delay)
    img_after_ops_path = f"./screenshot/screenshot_after_ops.png"
    get_screenshot(adb_path, save_path=img_after_ops_path)
    function_response = {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "name": tool_call["function"]["name"],
        "content": "快捷指令已从下发至设备，实现效果以屏幕效果为准",
    }
    return function_response, img_before_ops_path, img_after_ops_path, ops_detail


def handle_tool_calls(tool_calls, adb_path):
    logger.info(f"Handling tool calls: {len(tool_calls)} in total.")
    function_responses = []
    detailed_tool_call_infos = []
    img_before_ops_path, img_after_ops_path = None, None
    for tool_call in tool_calls:
        function_response = None
        ops_detail = []
        if tool_call["function"]["name"] == "controller":
            function_response, img_before_ops_path, img_after_ops_path, ops_detail = (
                control_handler(tool_call, adb_path)
            )
        elif tool_call["function"]["name"] == "shortcut":
            function_response, img_before_ops_path, img_after_ops_path, ops_detail = (
                shortcut_handler(tool_call, adb_path)
            )
        else:
            pass
        if function_response:
            function_responses.append(function_response)
        if len(ops_detail) > 0:
            detailed_tool_call_infos.extend(ops_detail)
    logger.info(f"TOTAL Tool calls responses: {function_responses}")
    logger.info(f"TOTAL Tool calls details: {detailed_tool_call_infos}")
    return (
        function_responses,
        img_before_ops_path,
        img_after_ops_path,
        detailed_tool_call_infos,
    )
