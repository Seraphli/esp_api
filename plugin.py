from appdirs import *
import codecs
import json
import asyncio
import socketio
import uuid
import sys
import re

APP_NAME = "electron-spirit"
PLUGIN_NAME = "ES API"
SHORT_NAME = "api"
PLUGIN_SETTING = "plugin.setting.json"
DEFAULT_CONFIG = {
    "input_hook": "api",
}


class PluginApi(socketio.AsyncClientNamespace):
    def __init__(self, parent):
        super().__init__()
        self.elem_count = 0
        self.parent = parent

    async def on_connect(self):
        print("Connected")
        await self.parent.setup_connect()

    def on_disconnect(self):
        print("Disconnected")

    def on_echo(self, data):
        print("Echo:", data)

    def on_addInputHook(self, data):
        print("Add input hook:", data)

    def on_delInputHook(self, data):
        print("Del input hook:", data)

    def on_insertCSS(self, data):
        print("Insert css:", data)

    def on_removeCSS(self, data):
        print("Remove css:", data)

    def on_addElem(self, data):
        print("Add elem:", data)
        self.elem_count += 1

    def on_delElem(self, data):
        print("Remove elem:", data)
        self.elem_count -= 1

    def on_showElem(self, data):
        print("Show view:", data)

    def on_hideElem(self, data):
        print("Hide view:", data)

    def on_setBound(self, data):
        print("Set bound:", data)

    def on_setContent(self, data):
        print("Set content:", data)

    def on_setOpacity(self, data):
        print("Set opacity:", data)

    def on_execJSInElem(self, data):
        print("Exec js in elem:", data)

    def on_notify(self, data):
        print("Notify:", data)

    def on_updateBound(self, key, bound):
        print("Update bound:", key, bound)

    def on_updateOpacity(self, key, opacity):
        print("Update opacity:", key, opacity)

    async def on_processContent(self, content):
        print("Process content:", content)
        await self.parent.process_content(content)

    def on_modeFlag(self, flags):
        print("Mode flag:", flags)

    def on_elemRemove(self, key):
        print("Elem remove:", key)
        return False

    def on_elemRefresh(self, key):
        print("Elem refresh:", key)
        return False


class APIHandler(object):
    def __init__(self, parent) -> None:
        self.parent = parent
        self.elems = {}

    def new_basic(self, content):
        catKey = f"api-{len(self.elems)}"
        basic = {
            "type": 0,
            "bound": {"x": -1, "y": -1, "w": -1, "h": -1},
            "content": content,
        }
        self.elems[catKey] = basic
        return catKey, basic

    def new_view(self, content):
        catKey = f"api-{len(self.elems)}"
        view = {
            "type": 1,
            "bound": {"x": -1, "y": -1, "w": -1, "h": -1},
            "content": content,
        }
        self.elems[catKey] = view
        return catKey, view

    async def api_processContent(self, data):
        print("Process content:", data)
        html = re.compile(r"<[^>]+>")
        http = re.compile(
            r"((([A-Za-z]{3,9}:(?:\/\/)?)(?:[-;:&=+$,\w]+@)?[A-Za-z0-9.-]+|(?:www.|[-;:&=+$,\w]+@)[A-Za-z0-9.-]+)((?:\/[+~%/.\w\-_]*)?\??(?:[-+=&;%@.\w_]*)#?(?:[.!/\\w]*))?)"
        )
        if html.match(data):
            await sio.emit(
                "addElem",
                data=(*self.new_basic(data),),
            )
        elif http.match(data):
            await sio.emit(
                "addElem",
                data=(*self.new_view(data),),
            )
        else:
            await sio.emit(
                "addElem",
                data=(*self.new_basic(f'<div class="card">{data}</div>'),),
            )

    async def api_notify(self, data):
        await sio.emit(
            "notify",
            data=(
                {
                    "text": data,
                    "title": PLUGIN_NAME,
                },
            ),
        )

    async def api_insertCSS(self, data):
        catKey, css = data.split("|")
        await sio.emit("insertCSS", data=(catKey, css))

    async def api_removeCSS(self, data):
        catKey, cssKey = data.split("|")
        await sio.emit("removeCSS", data=(catKey, cssKey))

    async def api_delElem(self, data):
        catKey = data
        if catKey not in self.elems:
            return
        await sio.emit("delElem", data=(catKey))

    async def api_showElem(self, data):
        catKey = data
        if catKey not in self.elems:
            return
        await sio.emit("showElem", data=(catKey))

    async def api_hideElem(self, data):
        catKey = data
        if catKey not in self.elems:
            return
        await sio.emit("hideElem", data=(catKey))

    async def api_js(self, data):
        catKey, code = data.split("|")
        if catKey not in self.elems:
            return
        await sio.emit(
            "execJSInElem",
            data=(
                catKey,
                code,
            ),
        )


class Plugin(object):
    def __init__(self) -> None:
        self.load_config()
        self.api = PluginApi(self)
        self.handler = APIHandler(self)

    def load_config(self):
        path = user_data_dir(APP_NAME, False, roaming=True)
        with codecs.open(path + "/api.json") as f:
            config = json.load(f)
        self.port = config["apiPort"]
        try:
            with codecs.open(PLUGIN_SETTING) as f:
                self.cfg = json.load(f)
            for k in DEFAULT_CONFIG:
                if k not in self.cfg or type(self.cfg[k]) != type(DEFAULT_CONFIG[k]):
                    self.cfg[k] = DEFAULT_CONFIG[k]
        except:
            self.cfg = DEFAULT_CONFIG
        self.save_cfg()

    def save_cfg(self):
        with codecs.open(PLUGIN_SETTING, "w") as f:
            json.dump(self.cfg, f)

    async def process_content(self, content):
        try:
            if " " in content:
                api, data = content.split(" ")
                for attr in dir(self.handler):
                    if attr.startswith("api_") and attr.endswith(api):
                        await getattr(self.handler, attr)(data)
                        return
                await self.handler.api_processContent(data)
            else:
                await self.handler.api_processContent(content)
        except:
            import traceback

            traceback.print_exc()

    async def setup_connect(self):
        # get input 'foo' from like 'g foo'
        await sio.emit("addInputHook", data=(self.cfg["input_hook"]))

    async def loop(self):
        await sio.connect(f"http://localhost:{self.port}")
        await sio.wait()


if __name__ == "__main__":
    # asyncio
    sio = socketio.AsyncClient()
    p = Plugin()
    sio.register_namespace(p.api)
    asyncio.run(p.loop())
