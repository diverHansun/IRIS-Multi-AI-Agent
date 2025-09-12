"""
Session control module for the Multi-AI-Agent project.
This module contains session management commands.
"""


def clear_session(ctx):
    """Clear current session memory"""
    if ctx.session_manager.clear_current_session():
        return {
            "type": "success",
            "message": "Current session memory cleared",
            "payload": {}
        }
    else:
        return {
            "type": "error",
            "message": "Failed to clear session memory",
            "payload": {}
        }


def new_session(ctx):
    """Create new session"""
    old_session_id = ctx.session_id
    ctx.session_id = ctx.session_manager.create_new_session()
    return {
        "type": "success",
        "message": f"New session created: {ctx.session_id}",
        "payload": {
            "old_session_id": old_session_id,
            "new_session_id": ctx.session_id
        }
    }


def list_sessions(ctx):
    """List session history"""
    sessions = ctx.global_memory.list_sessions()
    return {
        "type": "list",
        "message": f"Found {len(sessions)} sessions",
        "payload": {
            "sessions": sessions,
            "current_session_id": ctx.session_id
        }
    }


def restore_session(ctx, target_session_id: str):
    """Restore specified session"""
    if ctx.session_manager.switch_to_session(target_session_id):
        ctx.session_id = target_session_id
        session_info = ctx.global_memory.get_session_info(target_session_id)
        if session_info:
            return {
                "type": "success",
                "message": f"Switched to session: {target_session_id}",
                "payload": {
                    "session_id": target_session_id,
                    "session_info": session_info
                }
            }
        else:
            return {
                "type": "success",
                "message": f"Switched to session: {target_session_id}",
                "payload": {
                    "session_id": target_session_id
                }
            }
    else:
        return {
            "type": "error",
            "message": f"Session does not exist: {target_session_id}",
            "payload": {}
        }


def delete_session(ctx, target_session_id: str):
    """Delete specified session"""
    # Check if session exists
    if ctx.global_memory.session_exists(target_session_id):
        # Delete session
        if ctx.global_memory.storage.delete_session(target_session_id):
            # If deleting current session, create new session
            if target_session_id == ctx.session_id:
                ctx.session_id = ctx.session_manager.create_new_session()
                return {
                    "type": "success",
                    "message": f"Session deleted: {target_session_id}. New session created: {ctx.session_id}",
                    "payload": {
                        "deleted_session_id": target_session_id,
                        "new_session_id": ctx.session_id
                    }
                }
            else:
                return {
                    "type": "success",
                    "message": f"Session deleted: {target_session_id}",
                    "payload": {
                        "deleted_session_id": target_session_id
                    }
                }
        else:
            return {
                "type": "error",
                "message": f"Failed to delete session: {target_session_id}",
                "payload": {}
            }
    else:
        return {
            "type": "error",
            "message": f"Session does not exist: {target_session_id}",
            "payload": {}
        }


def cleanup_sessions(ctx):
    """Clean up orphaned sessions"""
    # Clean up orphaned sessions
    cleanup_stats = ctx.session_manager.cleanup_orphaned_sessions()
    return {
        "type": "success",
        "message": "Session cleanup completed",
        "payload": cleanup_stats
    }