import sys
import os
import io

# Create a dummy fcntl module
class DummyFcntl:
    def ioctl(self, *args, **kwargs):
        return 0

sys.modules['fcntl'] = DummyFcntl()

# Create a dummy termios module
class DummyTermios:
    TIOCGWINSZ = 0x40087468  # This is a dummy value, actual value doesn't matter on Windows

sys.modules['termios'] = DummyTermios()

# Add StringIO compatibility for Python 3
sys.modules['StringIO'] = io 