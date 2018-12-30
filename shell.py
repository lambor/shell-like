import sys
import termios
import types
import fcntl
import struct
import re

def getch():
    return sys.stdin.read(1)[0]

# https://gist.github.com/jtriley/1108174
def get_console_size_linux():
    def ioctl_GWINSZ(fd):
        try:
            cr = struct.unpack('hh',fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
            return cr
        except:
            pass
    return ioctl_GWINSZ(0)

class History:
    """ shell input history """

    def __init__(self):
        self.data = []
        self.tmp = None
        self.index = 0

    def add(self, line):
        if line:
            self.tmp = None
            self.data.append(line)
            self.index = len(self.data)

    def last(self, buf):
        if self.index > 0:
            if self.tmp is None:
                self.tmp = buf
            self.index -= 1
            return self.data[self.index]
        else:
            return None

    def next(self):
        if self.index < len(self.data)-1:
            self.index += 1
            return self.data[self.index]
        elif self.index == len(self.data)-1:
            self.index += 1
            return self.tmp
        else:
            return None


class Shell():

    def __enter__(self):
        self.orig_tty_settings = termios.tcgetattr(sys.stdin)
        new_settings = termios.tcgetattr(sys.stdin)
        new_settings[3] = new_settings[3] & ~(termios.ICANON)
        new_settings[3] = new_settings[3] & ~(termios.ECHO)
        termios.tcsetattr(sys.stdin, termios.TCSANOW, new_settings)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.orig_tty_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN,
                              self.orig_tty_settings)

    def __init__(self, prompt = '> ', auto_complete = None):
        self.prompt = prompt
        self.buf = ''
        self.bufwidth = 0  # record buf width
        self.c_pos = 0   # cursor position
        self.c_index = 0  # character position
        self.history = History()
        self.prompt_string = '' if type(prompt) is types.FunctionType else str(prompt) # lazy init prompt string
        self.auto_complete = auto_complete

    def __erase_overlap(self, old_c_pos, old_line_width, new_line_width):
        overlap_width = old_line_width - new_line_width
        shift_2_end = old_line_width - old_c_pos
        return (' '*shift_2_end + '\b'*overlap_width + ' '*overlap_width) if overlap_width > 0 else ''

    def __remove_color_str(self,string):
        return re.sub('\033\[[0-9;]*m','',string)

    def __refresh_buffer(self, new_line, new_c_pos, new_c_index):
        promptstr = self.__get_prompt_string()
        promptwidth = self.__string_width(self.__remove_color_str(promptstr))
        oldlinewidth = self.bufwidth
        newlinewidth = self.__string_width(new_line)

        sys.stdout.write(
            self.__erase_overlap(self.c_pos, oldlinewidth, newlinewidth) +
            # ensure reset cursor to left
            "\b"*(max(newlinewidth, oldlinewidth) + promptwidth + 1) +
            promptstr +  # prompt content
            new_line +  # new content
            "\b"*(newlinewidth - new_c_pos)  # set cursor to newpos
        )
        sys.stdout.flush()

        self.__update_shell(new_line, new_c_pos, new_c_index, newlinewidth)

    def __search_preceding_word(self, line, offset):
        found = False
        for i in range(min(len(line)-1, offset-1), -1, -1):
            if line[i] != ' ':
                found = True
            elif found:
                return i+1, offset
        return 0, offset

    def __update_shell(self, new_line, new_c_pos, new_c_index, new_line_width):
        self.buf = new_line
        self.c_pos = new_c_pos
        self.c_index = new_c_index
        self.bufwidth = new_line_width

    def __update_prompt_string(self):
        if type(self.prompt) is types.FunctionType:
            self.prompt_string = self.prompt()

    def __get_prompt_string(self):
        return self.prompt_string

    def __show_prompt(self):
        self.__update_shell('', 0, 0, 0)
        self.__update_prompt_string()
        sys.stdout.write(self.__get_prompt_string())
        sys.stdout.flush()

    def __show_auto_complete_hints(self,hints):
        max_length = max(len(hint) for hint in hints)
        max_width = max_length * 2 + 2 # hack, asume all chars are wchar, padding = 2
        screen_width = get_console_size_linux()[1]
        cols, output, l = max(screen_width//max_width,1), '', len(hints)
        for i in range(l):
            if i % cols == 0:
                print(output)
                output = ''
            output = output + '{: <{}}'.format(hints[i],(max_length+2))
        if output:
            print(output)

    def __is_wchar(self, char_code):  # 中文, 全角英文,　等
        # return char_code >= 0x2e80 and char_code <= 0x9fff
        return char_code >= 0x2e80

    def __string_width(self, string, l=None, r=None):
        if l is None:
            l = 0
        else:
            l = max(0, l)
        if r is None:
            r = len(string)
        width = 0
        while l < r:
            width += 2 if self.__is_wchar(ord(string[l])) else 1
            l = l+1
        return width

    def run(self, onCommand=None):
        self.__show_prompt()
        while True:
            new_line, new_c_pos, new_c_index = self.buf, self.c_pos, self.c_index

            char = getch()
            char_code = ord(char)

            if char_code == 4:  # EOT
                if not new_line:
                    break

            elif char_code == 1:  # CTRL+A
                new_c_pos = 0
                new_c_index = 0

            elif char_code == 5:  # CTRL+E
                l = len(new_line)
                new_c_pos = new_c_pos + \
                    self.__string_width(new_line, new_c_index, l)
                new_c_index = l

            elif char_code == 10:  # newline
                new_line = new_line + char  # only append a newline char
                new_c_pos = new_c_pos + \
                    self.__string_width(new_line, new_c_index, len(new_line))
                # new_c_index = len(new_line) # not necessary

            elif char_code == 21:  # CTRL+U
                new_line = new_line[new_c_index:]
                new_c_pos = 0
                new_c_index = 0

            elif char_code == 23:  # CTRL+W
                ds, de = self.__search_preceding_word(new_line, new_c_pos)
                dw = self.__string_width(new_line, ds, de)
                new_line = new_line[:ds] + new_line[de:]
                new_c_pos = new_c_pos - dw
                new_c_index = new_c_index - (de-ds)

            elif char_code == 27:  # ESC
                y = getch()
                z = getch()
                if ord(y) == 91:
                    code_z = ord(z)
                    if code_z == 65:  # UP ARROW
                        last_cmd = self.history.last(self.buf)
                        if last_cmd != None:
                            new_line = last_cmd
                            new_c_pos = self.__string_width(new_line)
                            new_c_index = len(new_line)

                    elif code_z == 66:  # DOWN ARROW
                        next_cmd = self.history.next()
                        if next_cmd != None:
                            new_line = next_cmd
                            new_c_pos = self.__string_width(new_line)
                            new_c_index = len(new_line)

                    elif code_z == 67:  # RIGHT ARROW
                        i = min(len(new_line), new_c_index+1)
                        new_c_pos = new_c_pos + \
                            self.__string_width(new_line, new_c_index, i)
                        new_c_index = i

                    elif code_z == 68:  # LEFT ARROW
                        i = max(0, new_c_index-1)
                        new_c_pos = new_c_pos - \
                            self.__string_width(new_line, i, new_c_index)
                        new_c_index = i

            elif char_code == 0x7f:  # backspace
                i = max(0, new_c_index-1)
                dw = self.__string_width(new_line, i, new_c_index)
                new_line = new_line[:i] + new_line[new_c_index:]
                new_c_pos = new_c_pos - dw
                new_c_index = i
            
            elif char_code == 9: # tab
                if self.auto_complete and new_c_index:
                    prefixes = new_line[:new_c_index].split()
                    if prefixes:
                        hints = self.auto_complete(prefixes[-1])
                        if hints:
                            self.__show_auto_complete_hints(hints)

            else:  # insert normal char
                # if char_code == 9:  # tab
                    # char = ' '*4
                new_line = new_line[:new_c_index] + \
                    char + new_line[new_c_index:]
                new_c_pos = new_c_pos + self.__string_width(char)
                new_c_index = new_c_index + len(char)

            # print(new_line,new_c_pos,new_c_index)
            # new_c_pos = max(0, min(len(new_line), new_c_pos))
            self.__refresh_buffer(new_line, new_c_pos, new_c_index)

            if char_code == 10:  # newline
                cmdline = new_line.strip()
                self.history.add(cmdline)

                if onCommand:
                    onCommand(cmdline)

                self.__show_prompt()


if __name__ == "__main__":
    import time
    with Shell(prompt = lambda: "\033[38;5;2mlambor\033[0m " + time.strftime("%Y-%m-%d %H:%M:%S") +"> ", 
        auto_complete = lambda predix: ['a','hello','where','1234567','jjjjjjjjjjjjjjjj','1','2','3']) as shell:
        shell.run(onCommand = lambda cmdline: print("your input: " + cmdline))