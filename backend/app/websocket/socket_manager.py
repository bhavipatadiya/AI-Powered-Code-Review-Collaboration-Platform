"""
socket_manager.py
Socket.IO server with:
  - Project rooms (join_project / leave_project)
  - Typing indicators
  - Online user tracking (in-memory)
  - User-specific rooms for personal notifications
  - Join / leave notifications
"""
import socketio

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

socket_app = socketio.ASGIApp(sio)

_room_members: dict = {}

def _room_key(project_id) -> str:
    return f"project_{project_id}"

def _get_online(room: str) -> list:
    members = _room_members.get(room, {})
    return sorted(set(members.values()))

@sio.event
async def connect(sid, environ, auth=None):
    print(f"[socket] connect sid={sid}")

@sio.event
async def disconnect(sid):
    print(f"[socket] disconnect sid={sid}")
    for room, members in list(_room_members.items()):
        if sid in members:
            username   = members.pop(sid)
            online     = _get_online(room)
            project_id = room.replace("project_", "")
            try:
                await sio.emit("user_left", {
                    "username":     username,
                    "online":       online,
                    "online_count": len(online),
                    "project_id":   project_id,
                }, room=room)
            except Exception:
                pass

@sio.event
async def join_project(sid, data):
    """
    Client emits: { project_id: 15, username: "Bhavi", user_id: 3 }
    """
    if not isinstance(data, dict):
        return

    project_id = str(data.get("project_id", ""))
    username   = data.get("username") or "Guest"
    user_id    = data.get("user_id")
    room       = _room_key(project_id)

    await sio.enter_room(sid, room)

    if room not in _room_members:
        _room_members[room] = {}
    _room_members[room][sid] = username

    online = _get_online(room)

    try:
        await sio.emit("user_joined", {
            "username":     username,
            "online":       online,
            "online_count": len(online),
            "project_id":   project_id,
        }, room=room)
    except Exception:
        pass

    if user_id:
        try:
            await sio.enter_room(sid, f"user_{user_id}")
        except Exception:
            pass

@sio.event
async def leave_project(sid, data):
    if not isinstance(data, dict):
        return
    project_id = str(data.get("project_id", ""))
    room       = _room_key(project_id)
    username   = (_room_members.get(room) or {}).pop(sid, "Unknown")

    try:
        await sio.leave_room(sid, room)
    except Exception:
        pass

    online = _get_online(room)
    try:
        await sio.emit("user_left", {
            "username":     username,
            "online":       online,
            "online_count": len(online),
            "project_id":   project_id,
        }, room=room)
    except Exception:
        pass

@sio.event
async def join_user_room(sid, data):
    if not isinstance(data, dict):
        return
    user_id = data.get("user_id")
    if user_id:
        try:
            await sio.enter_room(sid, f"user_{user_id}")
        except Exception:
            pass

@sio.event
async def typing_start(sid, data):
    if not isinstance(data, dict):
        return
    project_id = str(data.get("project_id", ""))
    room       = _room_key(project_id)
    try:
        await sio.emit("typing", {
            "username":   data.get("username", "Someone"),
            "project_id": project_id,
            "typing":     True,
        }, room=room, skip_sid=sid)
    except Exception:
        pass


@sio.event
async def typing_stop(sid, data):
    if not isinstance(data, dict):
        return
    project_id = str(data.get("project_id", ""))
    room       = _room_key(project_id)
    try:
        await sio.emit("typing", {
            "username":   data.get("username", "Someone"),
            "project_id": project_id,
            "typing":     False,
        }, room=room, skip_sid=sid)
    except Exception:
        pass

@sio.event
async def chat_message(sid, data):
    try:
        await sio.emit("chat_message", data)
    except Exception:
        pass

@sio.event
async def notification(sid, data):
    try:
        await sio.emit("notification", data)
    except Exception:
        pass

@sio.event
async def activity_update(sid, data):
    try:
        await sio.emit("activity_update", data)
    except Exception:
        pass

@sio.event
async def comment_added(sid, data):
    try:
        await sio.emit("comment_added", data)
    except Exception:
        pass
