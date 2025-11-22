#!/usr/bin/env python3
# -*- coding: utf-8 -*-
class CytubeError(Exception):
    ''' Base class for all exceptions in the cytube_bot package '''

class ProxyConfigError(CytubeError):
    ''' Exception raised when there is an error in the proxy configuration '''

class SocketConfigError(CytubeError):
    ''' Exception raised when there is an error in the socket configuration '''

class LoginError(CytubeError):
    ''' Exception raised when there is an error in the login process '''

class Kicked(CytubeError):  # noqa: N818 (legacy exception name)
    ''' Exception raised when the bot is kicked from the channel '''

class ChannelError(CytubeError):
    ''' Exception raised when there is an error in the channel '''

class ChannelPermissionError(ChannelError):
    ''' Exception raised when there is an error in the channel permissions '''

class SocketIOError(Exception):
    ''' Base class for all exceptions in the socketio package '''

class ConnectionFailed(SocketIOError):  # noqa: N818 (legacy exception name)
    ''' Exception raised when the connection to the server fails '''

class ConnectionClosed(SocketIOError):  # noqa: N818 (legacy exception name)
    ''' Exception raised when the connection to the server is closed '''

class PingTimeout(ConnectionClosed):
    ''' Exception raised when the connection to the server times out '''
