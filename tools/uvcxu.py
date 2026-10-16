# Minimal UVC extension-unit (XU) query helper. Run directly to dump current XU values:
#   python3 uvcxu.py [/dev/videoN]
import fcntl, os, struct, ctypes, sys
IOC = 0xC0107521  # UVCIOC_CTRL_QUERY
Q = dict(cur=0x81, min=0x82, max=0x83, len=0x85, info=0x86, defv=0x87)
def query(fd, unit, sel, q, size, data=None):
    buf = (ctypes.c_uint8 * max(size,1))(*(data or []))
    s = struct.pack("BBBxHxxP", unit, sel, q, size, ctypes.addressof(buf))
    fcntl.ioctl(fd, IOC, bytearray(s))
    return list(buf)[:size]
def length(fd, unit, sel):
    return struct.unpack("<H", bytes(query(fd, unit, sel, Q["len"], 2)))[0]
if __name__ == "__main__":
    fd = os.open(sys.argv[1] if len(sys.argv) > 1 else "/dev/video2", os.O_RDWR)
    for unit, sel in [(4,2),(4,3),(4,4),(4,5),(4,6),(4,7),(4,8),(4,9),(5,2),(5,4),(7,2),(7,3),(7,6),(7,9)]:
        try:
            n = length(fd, unit, sel)
            print(unit, sel, "len", n, "cur", query(fd, unit, sel, Q["cur"], n), "def", query(fd, unit, sel, Q["defv"], n))
        except OSError as e:
            print(unit, sel, "err", e)
