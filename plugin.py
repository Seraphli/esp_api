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

    def on_connect(self):
        print("Connected")

    def on_disconnect(self):
        print("Disconnected")
        sys.exit(0)

    def on_echo(self, data):
        print("Echo:", data)

    def on_register_topic(self, data):
        print("Register topic:", data)

    def on_add_input_hook(self, data):
        print("Add input hook:", data)

    def on_del_input_hook(self, data):
        print("Del input hook:", data)

    def on_insert_css(self, data):
        print("Insert css:", data)

    def on_remove_css(self, data):
        print("Remove css:", data)

    def on_update_elem(self, data):
        print("Update elem:", data)

    def on_remove_elem(self, data):
        print("Remove elem:", data)

    def on_show_view(self, data):
        print("Show view:", data)

    def on_hide_view(self, data):
        print("Hide view:", data)

    def on_exec_js_in_elem(self, data):
        print("Exec js in elem:", data)

    def on_notify(self, data):
        print("Notify:", data)

    def on_update_bound(self, key, _type, bound):
        print("Update bound:", key, _type, bound)

    async def on_process_content(self, content):
        print("Process content:", content)
        await self.parent.process_content(content)

    def on_mode_flag(self, lock_flag, move_flag, dev_flag):
        print("Mode flag:", lock_flag, move_flag, dev_flag)

    def on_elem_activated(self, key):
        print("Elem activated:", key)

    def on_elem_deactivated(self, key):
        print("Elem deactivated:", key)


class APIHandler(object):
    def __init__(self, parent) -> None:
        self.parent = parent
        self.elems = {}
    
    @property
    def ctx(self):
        return self.parent.ctx

    def new_basic(self, content):
        key = f"basic-{len(self.elems)}"
        basic = {
            "key": key,
            "type": 0,
            "bound": {"x": -1, "y": -1, "w": -1, "h": -1},
            "content": content,
        }
        self.elems[key] = basic
        return basic

    def new_view(self, content):
        key = f"view-{len(self.elems)}"
        view = {
            "key": key,
            "type": 1,
            "bound": {"x": -1, "y": -1, "w": -1, "h": -1},
            "content": content,
        }
        self.elems[key] = view
        return view

    async def api_process_content(self, data):
        print("Process content:", data)
        html = re.compile(r"<[^>]+>")
        css = re.compile(
            r"([#.@]?[\w.:> ]+)[\s]{[ ]*[\r\n]*([A-Za-z\-\r\n\t]+[:][\s]*[\w ./()\-!,]+;[\r\n]*(?:[A-Za-z\- \r\n\t]+[:][\s]*[\w ./()\-!,]+;[\r\n]*)*)[ ]*}"
        )
        http = re.compile(
            r"((([A-Za-z]{3,9}:(?:\/\/)?)(?:[-;:&=+$,\w]+@)?[A-Za-z0-9.-]+|(?:www.|[-;:&=+$,\w]+@)[A-Za-z0-9.-]+)((?:\/[+~%/.\w\-_]*)?\??(?:[-+=&;%@.\w_]*)#?(?:[.!/\\w]*))?)"
        )
        if html.match(data):
            await sio.emit(
                "update_elem",
                data=(
                    self.ctx,
                    self.new_basic(data),
                ),
            )
        elif http.match(data):
            await sio.emit(
                "update_elem",
                data=(
                    self.ctx,
                    self.new_view(data),
                ),
            )
        elif css.match(data):
            await sio.emit("insert_css", data=(self.ctx, data))
        else:
            await sio.emit(
                "update_elem",
                data=(
                    self.ctx,
                    self.new_basic(f'<div class="card">{data}</div>'),
                ),
            )

    async def api_notify(self, data):
        await sio.emit(
            "notify",
            data=(
                self.ctx,
                {
                    "text": data,
                    "title": PLUGIN_NAME,
                },
            ),
        )

    async def api_insert_css(self, data):
        await sio.emit("insert_css", data=(self.ctx, data))

    async def api_remove_css(self, data):
        await sio.emit("remove_css", data=(self.ctx, data))

    async def api_remove_elem(self, data):
        key = data
        if key not in self.elems:
            return
        await sio.emit("remove_elem", data=(self.ctx, data))

    async def api_show_view(self, data):
        key = data
        if key not in self.elems or self.elems[key]["type"] != 1:
            return
        await sio.emit("show_view", data=(self.ctx, self.elems[key]))

    async def api_hide_view(self, data):
        key = data
        if key not in self.elems or self.elems[key]["type"] != 1:
            return
        await sio.emit("hide_view", data=(self.ctx, self.elems[key]))

    async def api_js(self, data):
        key, cmd = data.split(" ")
        if key not in self.elems:
            return
        await sio.emit(
            "exec_js_in_elem",
            data=(
                self.ctx,
                self.elems[key],
                cmd,
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
                await self.handler.api_process_content(data)
            else:
                await self.handler.api_process_content(content)
        except:
            import traceback
            traceback.print_exc()

    async def register(self):
        # Create a context for registering plugins
        # You can either use sample password or use complex password
        # You can also register multiple topic
        ctx = {"topic": SHORT_NAME, "pwd": str(uuid.uuid4())}
        await sio.emit("register_topic", ctx)
        self.ctx = ctx

    async def wait_for_elem(self):
        while self.api.elem_count < 2:
            await asyncio.sleep(0.1)

    async def test_case(self):
        # get input 'foo' from like 'g foo'
        await sio.emit("add_input_hook", data=(self.ctx, self.cfg["input_hook"]))

    async def loop(self):
        await sio.connect(f"http://localhost:{self.port}")
        await self.register()
        await self.test_case()
        await sio.wait()


if __name__ == "__main__":
    # asyncio
    sio = socketio.AsyncClient()
    p = Plugin()
    sio.register_namespace(p.api)
    asyncio.run(p.loop())
