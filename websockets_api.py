import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
import subprocess
import os
import time
from PIL import Image
import io
import argparse
import atexit
import random


def queue_prompt(prompt, server_address, client_id):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_images(ws, prompt, server_address, client_id):
    prompt_id = queue_prompt(prompt, server_address, client_id)["prompt_id"]
    output_images = {}
    current_node = ""
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "executing":
                data = message["data"]
                if data["prompt_id"] == prompt_id:
                    if data["node"] is None:
                        break  # Execution is done
                    else:
                        current_node = data["node"]
        else:
            if current_node == "save_image_websocket_node":
                images_output = output_images.get(current_node, [])
                images_output.append(out[8:])
                output_images[current_node] = images_output

    return output_images


def connect_with_infinite_retry(server_address, client_id, retry_interval=0.3):
    ws = websocket.WebSocket()

    while True:
        try:
            ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
            print("WebSocket connection successful.")
            return ws
        except websocket.WebSocketException as e:
            print(f"Connection attempt failed: {e}")
        except ConnectionRefusedError:
            print(
                "Connection refused, ensure the server is up and accepting connections."
            )
        except Exception as e:
            print(f"Unexpected error: {e}")

        time.sleep(retry_interval)


def close_serv(proc):
    def close():
        print("Closing serv...")
        proc.kill()

    return close


def main_prosess(prompt, mode, save_path):

    # ===Update user data===

    data = {
        "prompt": prompt,
        "mode": int(mode),
        "work": "Pony_Diffusion_V6_XL_Basic",
        "seed": [random.getrandbits(64)],
    }

    # =======================

    script_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = [
        "python",
        os.path.join(script_dir, "ComfyUI/main.py"),
        "--listen=127.0.0.1",
        "--dont-print-server",
    ]
    proc = subprocess.Popen(cmd)
    atexit.register(close_serv(proc))

    server_address = "127.0.0.1:8188"
    client_id = str(uuid.uuid4())

    prompt = {}

    if data["mode"] == 1:
        with open(os.path.join(script_dir, "landscape/api.json"), "r") as file:
            prompt = json.load(file)
    else:
        with open(os.path.join(script_dir, "portait/api.json"), "r") as file:
            prompt = json.load(file)

    # ===Update prompt with user data===

    prompt["6"]["inputs"]["text"] = prompt["6"]["inputs"]["text"].format(
        userprompt=data["prompt"]
    )
    prompt["3"]["inputs"]["seed"] = data["seed"][0]

    # =======================

    ws = connect_with_infinite_retry(server_address, client_id)
    images = get_images(ws, prompt, server_address, client_id)
    for node_id in images:
        for image_data in images[node_id]:
            image = Image.open(io.BytesIO(image_data))
            image.save(save_path, format="PNG")
            return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=int)
    parser.add_argument("--prompt", type=str)
    parser.add_argument("--save_path", type=str)
    args = parser.parse_args()

    main_prosess(
        args.prompt,
        args.mode,
        args.save_path,
    )
