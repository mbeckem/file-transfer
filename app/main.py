import asyncio
import aiohttp
import collections
import concurrent
import functools
import json
import logging
import string
import time
import traceback

from aiohttp import web
from enum import Enum, unique

from .channel import Channel, ChannelEmpty, ChannelClosed
from .json_types import JsonError, parse_as, get_as, assert_as

File = collections.namedtuple("File", ["name", "size", "type"])

logger = logging.getLogger(__name__)

valid_filename_chars = "-_.() {0}{1}".format(
    string.ascii_letters, string.digits)


def sanitize_filename(name):
    name = "".join(c for c in name if c in valid_filename_chars)
    name = name.strip()[:256]
    if not name:
        name = "file.bin"
    return name


class Session:
    """A session represents a single in-progress file upload."""

    def __init__(self, id, file):
        self.id = id
        self.file = file
        self.status_future = asyncio.Future()
        self.upload_future = asyncio.Future()
        self.download_future = asyncio.Future()
        self.timed_out = False
        self.done_event = asyncio.Event()
        self.task = asyncio.async(self.run())
        self.task.add_done_callback(self._task_completed)

    @asyncio.coroutine
    def run(self):
        logger.debug("Session %s: started", self.id)

        status_channel = None
        upload = None
        download = None
        try:
            # Uploader must connect quickly.
            try:
                wait_future = asyncio.gather(
                    self.status_future, self.upload_future)
                ignoreFailure(wait_future)
                [status_channel, upload] = yield from asyncio.wait_for(wait_future, timeout=5.0)
                logger.debug(
                    "Session %s: uploader and status channel arrived", self.id)
            except asyncio.TimeoutError:
                self.timed_out = True
                logger.info("Session %s: timed out", self.id)
                return

            # Session stays valid for two hours.
            try:
                timeout = 2 * 60 * 60
                download = yield from asyncio.wait_for(self.download_future, timeout=timeout)
                logger.debug("Session %s: downloader arrived", self.id)
            except asyncio.TimeoutError:
                self.timed_out = True
                status_channel.try_put({"type": "timeout"})
                logger.info("Session %s: timed out", self.id)
                return

            try:
                yield from self._copy(upload, download, status_channel)
                logger.debug("Session %s: copy complete", self.id)
            except:
                status_channel.try_put({"type": "error"})
                raise

        finally:
            self.done_event.set()

    # The status connection uses a websocket to update
    # the uploading user's website.
    # The user will receive progress events such as
    # the number of written bytes and errors.
    @asyncio.coroutine
    def status_response(self, request):
        if self.timed_out or self.status_future.done():
            logger.debug("Session %s: invalid status request", self.id)
            return web.HTTPNotFound(text="Cannot connect to this session")

        ws = web.WebSocketResponse()
        ws.start(request)

        ch = Channel()
        self.status_future.set_result(ch)
        asyncio.async(self.done_event.wait()) \
            .add_done_callback(lambda task: ch.close())

        reader_task = None
        writer_task = None

        @asyncio.coroutine
        def writer():
            try:
                msg = None
                while True:
                    msg = yield from ch.get()
                    if ws.closed:
                        break
                    ws.send_str(json.dumps(msg))
            except ChannelClosed:
                pass
            finally:
                reader_task.cancel()

        @asyncio.coroutine
        def reader():
            try:
                while True:
                    msg = yield from ws.receive()
                    if msg.tp == aiohttp.MsgType.text:
                        # print("websocket client should only read")
                        break
                    elif msg.tp == aiohttp.MsgType.close:
                        self.task.cancel()
                        logger.error("Session %s: websocket closed", self.id)
                        break
                    elif msg.tp == aiohttp.MsgType.error:
                        self.task.cancel()
                        logger.error("Session %s: websocket error - %s",
                                     self.id, ws.exception())
                        break
            finally:
                writer_task.cancel()

        writer_task = asyncio.async(writer())
        reader_task = asyncio.async(reader())

        try:
            yield from reader_task
            yield from writer_task
        finally:
            ch.close()
            yield from ws.close()
            logger.debug("Session %s: status response done", self.id)

        return ws

    # The upload connection receives as file via POST request
    # and registers it with the sessions main coroutine.
    # This coroutine waits until the transfer is complete and then
    # replies with "Ok".
    @asyncio.coroutine
    def upload_response(self, request):
        if self.timed_out or self.upload_future.done():
            logger.debug("Session %s: invalid upload request", self.id)
            return web.HTTPNotFound(text="Cannot upload to this session")

        self.upload_future.set_result(request)
        yield from self.done_event.wait()

        logger.debug("Session %s: upload done", self.id)
        return web.HTTPOk(text="Ok")

    # The download connection is used by the receiver of the file
    # to download the file via HTTP. The request is registered
    # with the main coroutine and this coroutine waits until the transfer is
    # complete.
    @asyncio.coroutine
    def download_response(self, request):
        if self.timed_out or self.download_future.done():
            logger.debug("Session %s: invalid download request", self.id)
            return web.HTTPNotFound(text="Cannot download from this session")

        response = web.StreamResponse()
        response.set_status(200)
        response.content_type = "application/octet-stream"
        response.content_length = self.file.size
        response.headers[
            "Content-Disposition"] = "attachment; filename=\"{}\"".format(self.file.name)
        response.force_close()
        response.start(request)

        self.download_future.set_result(response)
        yield from self.done_event.wait()
        yield from response.write_eof()

        logger.debug("Session %s: download done", self.id)
        return response

    _READ_SIZE = 256 * 1024

    # Copies the file from the upload to the download connection
    # and notifies the status_channel about any progress made.
    @asyncio.coroutine
    def _copy(self, upload_request, download_response, status_channel):
        reader = upload_request.content

        status_channel.put({"type": "start"})

        done = 0
        pending = self.file.size
        last_progress = None
        while pending != 0:
            n = min(pending, self._READ_SIZE)
            data = yield from reader.readexactly(n)
            download_response.write(data)
            yield from download_response.drain()

            done += n
            pending -= n

            # Send progress updates at most once every 0.5 seconds
            now = time.time()
            if last_progress is None or (now - last_progress) >= 0.5:
                if status_channel.pending() > 60:
                    raise RuntimeError("Very slow status channel")
                status_channel.put(
                    {"type": "progress", "done": done, "size": self.file.size})
                last_progress = now

        status_channel.put({"type": "done"})

    def _task_completed(self, task):
        if task.cancelled():
            logger.info("Session %s: cancelled", self.id)
        elif task.exception() is not None:
            try:
                raise task.exception()
            except:
                logger.exception("Session %s: failed with exception", self.id)
        else:
            logger.debug("Session %s: done", self.id)


class SessionRegistry:

    def __init__(self):
        self.sessions = {}
        self.nextID = 1

    def create(self, file):
        id = self.nextID
        session = Session(id, file)
        self.sessions[id] = session

        logger.info("Session %s: created (%s)", id, file)

        def on_done(task):
            logger.info("Session %s: destroyed", id)
            del self.sessions[id]

        session.task.add_done_callback(on_done)

        self.nextID += 1
        return id

    def count(self):
        return len(self.sessions)

    def get(self, id):
        return self.sessions.get(id, None)


@unique
class ApplicationType(Enum):
    dev = 1
    prod = 2


class Application:

    def __init__(self, apptype=ApplicationType.prod):
        self.loop = asyncio.get_event_loop()
        self.sessions = SessionRegistry()
        self.type = apptype
        self.app = web.Application(loop=self.loop)
        self.app.router.add_route("POST", "/api/create", self.create_transfer)
        self.app.router.add_route("GET", "/api/status", self.transfer_status)
        self.app.router.add_route("POST", "/u/{id}", self.start_upload)
        self.app.router.add_route("GET", "/d/{id}", self.start_download)
        self.running = False

        if self.type == ApplicationType.dev:
            logger.info("Development mode enabled. Registering static routes.")
            self.app.router.add_route("GET", "/", self.handle_index)
            self.app.router.add_static("/", "assets")

    def run(self):
        assert not self.running, "Run can only be called once at a time"

        self.running = True
        try:
            app = self.app
            loop = self.loop

            handler = app.make_handler()
            future = loop.create_server(handler, "0.0.0.0", 8080)
            server = loop.run_until_complete(future)
            status = asyncio.async(self.status_loop())

            logger.info("running server on port %s", 8080)
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                logger.info("keyboard interrupt")
                pass
            finally:
                loop.run_until_complete(handler.finish_connections(1.0))
                status.cancel()
                server.close()

                loop.run_until_complete(server.wait_closed())
                loop.run_until_complete(app.finish())
                loop.run_until_complete(status)

        finally:
            self.running = False

    def exit(self):
        if self.running:
            self.loop.close()

    @asyncio.coroutine
    def status_loop(self):
        try:
            while True:
                yield from asyncio.sleep(5 * 60.0)
                logger.info(
                    "Number of active sessions: %s", self.sessions.count())
        except concurrent.futures.CancelledError:
            pass

    @asyncio.coroutine
    def create_transfer(self, request):
        """Takes a file name, a file size and a mime type and
        eturns a transfer-id to the client."""
        try:
            data = parse_as((yield from request.text()), dict)
            fname = get_as(data, "name", str, default="")
            fsize = assert_as(data, "size", int)
            ftype = get_as(data, "type", str, default="")
        except (ValueError, KeyError, JsonError) as e:
            logger.error("Invalid file spec")
            return web.HTTPBadRequest(text="Invalid request format")

        if fsize <= 0:
            return web.HTTPBadRequest(text="Invalid file size")

        fname = sanitize_filename(fname)
        file = File(name=fname, size=fsize, type=ftype)
        id = self.sessions.create(file)
        return web.Response(text=str(id))

    @asyncio.coroutine
    def transfer_status(self, request):
        try:
            id = int(request.GET["id"])
        except (ValueError, KeyError) as e:
            logger.error("transfer_status: Invalid upload id")
            return web.HTTPBadRequest(text="Invalid upload id")

        session = self.sessions.get(id)
        if session is None:
            logger.error("transfer_status: Upload id %s does not exist", id)
            return web.HTTPNotFound(text="Upload id does not exist")

        return (yield from session.status_response(request))

    @asyncio.coroutine
    def start_upload(self, request):
        try:
            id = int(request.match_info["id"])
        except (ValueError, KeyError) as e:
            logger.error("start_upload: Invalid upload id")
            return web.HTTPBadRequest(text="Invalid upload id")

        session = self.sessions.get(id)
        if session is None:
            logger.error("start_upload: Upload id %s does not exist", id)
            return web.HTTPNotFound(text="Upload id does not exist")

        return (yield from session.upload_response(request))

    @asyncio.coroutine
    def start_download(self, request):
        try:
            id = int(request.match_info["id"])
        except (ValueError, KeyError) as e:
            logger.error("start_download: Invalid download id")
            return web.HTTPBadRequest(text="Invalid download id")

        session = self.sessions.get(id)
        if session is None:
            logger.error("start_download: Download id %s does not exist", id)
            return web.HTTPNotFound(text="Download id does not exist")

        return (yield from session.download_response(request))

    @asyncio.coroutine
    def handle_index(self, request):
        with open("assets/index.html", "rb") as f:
            return web.Response(content_type="text/html; charset=utf-8",
                                body=f.read())


def ignoreFailure(future):
    def callback(future):
        if not future.cancelled():
            future.exception()  # Mark retrieval

    future.add_done_callback(callback)
