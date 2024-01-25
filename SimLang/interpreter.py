# I used black with --fast and --safe to format the code (some of it)
import os
import sys
import traceback
import shutil
import py_compile
from importlib import import_module
from random import choice as choose_random
from random import randint

## Handle local dir and where to put libs folder
os.chdir(os.getcwd())
LOCALDIR = os.getcwd() + "/"
del sys.path[0]
sys.path[0] = LOCALDIR
if os.name == "nt":
    HOST_OS = sys.platform
    LIBDIR = os.path.join(os.getenv("APPDATA"), "simlang_libs") + "\\"
    MODDIR = os.path.join(os.getenv("APPDATA"), "simlang_modules") + "\\"
elif os.name == "posix":
    HOST_OS = sys.platform
    LIBDIR = "~/simlang_libs/"
    MODDIR = "~/simlang_modules/"
else:
    HOST_OS = "Unknown"
    LIBDIR = "./dependencies/"
    MODDIR = "./modules/"
HOST_OS = HOST_OS.title()
LIBDIR = os.path.expanduser(LIBDIR)
MODDIR = os.path.expanduser(MODDIR)

## CONSTANTS
MAX_SCRIPT_CALLS = 20  # max number of scripts to call without waiting to finish
COMMENT = "//"
GLOBAL_CODE = ""

def read(tree, path):
    fpath = path.split("->")
    if len(fpath) != 1:
        if fpath[0] in tree:
            if type(tree[fpath[0]]) != dict:
                return 0
            return read(tree[fpath[0]], "->".join(fpath[1:]))
    else:
        return tree[fpath[0]] if fpath[0] in tree else 0


class module_capsule:
    """A class to encapsulate modules."""

    def __init__(self, module):
        self.module = module
        self.__call_to_lock()

    def Mreplace_module(self, module):
        if self.module == module:
            raise Exception("Module cannot be the same!")
        self.module = module

    @property
    def Mmodule(self):
        return self.module

    def __call_to_lock(self):
        def setattr(self, name, value):
            raise Exception("Module Capsule object is read only!")

        self.__setattr__ = setattr

    def __getattr__(self, other):
        return self.__dict__["module"].__dict__.get(other)

    def __repr__(self):
        return f"<Module Capsule for '{self.module.__name__}' in '{self.module.__file__}'>"


class data_node:
    def __init__(self, depth=None):
        self._depth = depth or 0

    def new_sector(self, name):
        if not name.isidentifier():
            raise NameError("Invalid name: " + name)
        self.__dict__[name] = data_node(self._depth + 1)

    def rem_sector(self, name):
        if not name.isidentifier() or name not in self.__dict__:
            raise NameError("Invalid name: " + name)
        self.__dict__.pop(name)

    def __contains__(self, other):
        return other in self.__dict__

    def __getitem__(self, name):
        return self.__dict__.get(name, None)

    def __repr__(self):
        return f"<data_node(depth={self._depth})>"


def getattrbypath(path, obj, sep="::"):
    """
    Get an attribute in a tree like object.
    'sep' is "::" by default
    >>> getattrbypath("path::isfile",os)(__file__)
    True
    >>> getattrbypath("path.isfile",os,".")(__file__)
    True
    """
    if len(path.split(sep)) == 1:
        return getattr(obj, path)
    return getattrbypath(sep.join(path.split(sep)[1:]), getattr(obj, path.split(sep)[0]), sep)


def hasattrbypath(path, obj, sep="::"):
    """
    Simmilar to getattrbypath but it returns a bool instead of the object.
    >>> hasattrbypath("path::isfile",os)
    True
    >>> hasattrbypath("path.isfile",os,".")
    True
    """
    if len(path.split(sep)) == 1:
        return hasattr(obj, path)
    return hasattrbypath(sep.join(path.split(sep)[1:]), getattr(obj, path.split(sep)[0]), sep)


def getfilename(path):
    """
    Get the file name of a path.
    >>> getfilename("path/dir/file.something.txt")
    file
    """
    name = os.path.basename(path).split(".")[::-1][-1]
    return name


def compress(items):
    """
    Compresses the list or tuple into a ordered tuple without duplicates.
    >>> compress([90,90,10,12,12])
    (90,10,12)
    """
    l = tuple()
    for item in items:
        if item not in l:
            l = tuple([*l, item])
    return l


def append(tup: tuple, item) -> tuple:
    """
    Return a tuple with the given item added to the end.
    >>> append((60,70),80)
    (60,70,80)
    """
    k = list(tup)
    k.append(item)
    return tuple(k)


def pop(tup: tuple):
    """
    Return the end of the tuple or list.
    >>> pop((90,))
    90
    >>> pop(tuple())
    None
    """
    return tup[-1] if tup else None


class inter_class:
    __slots__ = tuple("_exit_method classes current_line _default_scope _files _func _scope global_scope local_scope _jtable _mods _call_stack _calls data _ignore _iter _ns lines".split())

    def __init__(self, path, name="script:main"):
        self._exit_method = self.exit
        self._default_scope = {
            "_sys_host_os_name": os.name,
            "_sys_libdir": LIBDIR,
            "_sys_localdir": LOCALDIR,
            "_lib_OS": os,
            "_lib_SYS": sys,
            "_md_file": path,
            "_sys_scope_depth": 0,
        }
        self._scope = [self._default_scope.copy()]
        self.global_scope = self._scope[0]
        self.global_scope["_sys_max_recursive_calls"] = 10_000  # max calls without returning
        self.local_scope = self._scope[-1]
        self.classes = {"os": os, "sys": sys}
        self._jtable = {}
        self._mods = {}
        self._call_stack = tuple()
        self._calls = tuple()
        self.data = data_node()
        self._ignore = ["glabel","end"]
        self._iter = 0
        self._ns = None
        self.lines = tuple()
        self._files = [name]
        self._func = {}
    def is_func(self, name):
        if type(name) != str:
            self.err(f"[Error]: Invalid type for name!")
        elif not name.isidentifier():
            self.err(f"[Error]: Invalid name `{name}`")
        if name not in self._jtable or type(self._jtable.get(name)) != tuple:
            return False
        elif name in self._jtable and type(self._jtable.get(name)) == tuple:
            return True
        return False

    def is_label(self, name):
        if type(name) != str:
            self.err(f"[Error]: Invalid type for name!")
        elif not name.isidentifier():
            self.err(f"[Error]: Invalid name `{name}`")
        if name not in self._jtable or type(self._jtable.get(name)) != str:
            return False
        elif name in self._jtable and type(self._jtable.get(name)) == str:
            return True
        return False

    def new_scope(self):
        self._scope.append(self._default_scope.copy())
        self.local_scope = self._scope[-1]
        self.local_scope["_sys_scope_depth"] = len(self._scope) - 1

    def pop_scope(self):
        if len(self._scope) > 1:
            self._scope.pop()
            self.local_scope = self._scope[-1]
        else:
            self.err("[Error-Crit]: Cannot pop global scope!")

    def add_mod(self, name, args):
        def wrapper(func):
            self._mods[f"{self._ns}.{name}" if self._ns != None else name] = (
                lambda *x: func(self, *x)
                if ((len(x) == args) if args != -1 else (len(x) > 0))
                else self.err(func.__doc__ if func.__doc__ else f"[Error-Mod]: Miss matching arguments.\nExpected {args} but recieved {len(x)}."),
                True,
            )
            return func

        return wrapper

    def iadd_mod(self, args):
        def wrapper(func):
            self._mods[f"{self._ns}.{func.__name__}" if self._ns != None else func.__name__] = (
                lambda *x: func(self, *x)
                if ((len(x) == args) if args != -1 else (len(x) > 0))
                else self.err(func.__doc__ if func.__doc__ else f"[Error-Mod]: Miss matching arguments.\nExpected {args} but recieved {len(x)}.")
            )
            return func

        return wrapper

    @staticmethod
    def import_module(name):
        print("[Warning (include:module)]: some bugs are not fixed yet, do not report!")
        if not os.path.isfile(MODDIR + name): # If the main file is missing
            return None
        elif os.path.isfile(MODDIR + name):
            globs = {}
            exec(open(MODDIR + name).read(), globs)
            test =  type(name,(object,),globs)
            test.__str__ = lambda self: str(self.__dict__)
            return test
        return None

    def include(self, path):
        mod = {"inter": self, "__file__": LOCALDIR + "/" + path, "sys_host_os": os.name}
        self._ns = getfilename(path)
        if not os.path.isfile(LOCALDIR + path):
            self.err(
                f'[Error]: "{LOCALDIR+path}" is not an extension.\nIt wasn\'t found in the local directory!'
                + (f'\nDid you mean `include_std "{path}"`?\n"{path}" Was found in the libs directory.' if os.path.isfile(LIBDIR + path) else ""),
                force=True,
            )
        try:
            exec(compile(open(path).read(), path, "exec"), mod)
        except:
            self.err(traceback.format_exc())
        dependencies = mod.get("_lib_dependencies", [])
        for lib in dependencies:
            self._ns = lib
            self.include_std(lib)
        self._ignore.extend(mod.get("_sys_ignore", []))
        self._ns = None

    def include_std(self, path):
        mod = {"inter": self, "__file__": LOCALDIR + "/" + path, "sys_host_os": os.name}
        self._ns = getfilename(path)
        if not os.path.isfile(LIBDIR + path):
            self.err(
                f'[Error]: "{LIBDIR+path}" is not an extension.\nIt wasn\'t found in the libs directory!'
                + (f'\nDid you mean `include "{path}"`?\n"{path}" Was found in the local directory.' if os.path.isfile(LOCALDIR + path) else ""),
                force=True,
            )
        try:
            exec(compile(open(LIBDIR + path).read(), path, "exec"), mod)
        except:
            self.err(traceback.format_exc())
        self._ignore.extend(mod.get("_sys_ignore", []))
        self._ns = None
    
    def jumpto(self, prog, label, raise_error=True, offset=0, error_msg="Block not closed!"):
        """
        DO NOT USE FOR ANY OTHER PURPOSE.
        THIS FOR INTERNAL USE ONLY!
        Helper function to jump to a line equal to label.
        If your code in SimLang is like bellow:
        ```
        include_std "test.py"
        println "test"
        test:hello
        ```
        And when you call test.py which has the following code:
        ```
        inter.jumpto(prog, "test:hello")
        ```
        The var `prog` is a variable only accessible in the run method and thus
        only usable in the run method.
        It would skip println or any code between the include statement and the
        label specified in the label parameter.
        """
        oldp = self.current_line
        while self.current_line != len(prog):
            line = prog[self.current_line][0] if len(prog[self.current_line]) > 0 else ""
            if line == label:
                break
            self.current_line += 1
        else:
            if raise_error == False:
                return 1
            else:
                self.current_line = oldp
                self.err(error_msg)
        self.current_line += offset
        return 0

    def _values_nrt(self, args):
        for pos, arg in enumerate(args):
            ## Only literals
            if arg == ".none":
                args[pos] = 0
            elif arg == ".true":
                args[pos] = 1
            elif arg == ".false":
                args[pos] = 0
            elif arg.count("-") <= 1 and arg.replace("-", "").isdigit():  # Integer
                args[pos] = int(arg)
            elif arg.count("-") <= 1 and arg.count(".") <= 1 and arg.replace("-", "").replace(".", "").isdigit():  # Float
                args[pos] = float(arg)
            elif arg.isidentifier():
                pass
            elif arg.startswith('"') and arg.endswith('"'):
                args[pos] = arg[1:-1]
        return tuple(args)
   
    def call_function(self, name, *args):
        if not (name.isidentifier() or name in self._jtable or isinstance(self._jtable.get(name),tuple)):
            self.err("[Error]: Invalid name: " + name)
        jump, arg_name, defs = self._jtable[name]
        if jump == "partial:func":
            self.err(f"[Error]: Function `{ins}` not fully defined!")
        self._call_stack = append(self._call_stack, self.current_line)
        self.new_scope()
        if self._iter > self.global_scope.get("_sys_max_recursive_calls", 10_000):
            self.err(
                "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz]` for loops!",
                True,
            )
        self.current_line = jump
        self._iter += 1
        self.local_scope.update(defs)
        if len(args) < len(arg_name) and arg_name[len(tuple(zip(arg_name, args))) :] != tuple(defs.keys()):
            out = "Missed:\n"
            for name in arg_name[len(tuple(zip(arg_name, args))) :]:
                out += f" - {name}\n"
            out = out[:-1]
            self.err(f"[Error]: Mismatch in arguments! Function got less arguments than expected.\n{out}")
        if len(args) > len(arg_name):
            out = "Extra:\n"
            for name in args[len(tuple(zip(arg_name, args))) :]:
                out += f" - {name}\n"
            out = out[:-1]
            self.err(f"[Error]: Mismatch in arguments! Function got more arguments than expected.\n{out}")
        for name, val in zip(arg_name, args):
            if val == ".ignore:arg":
                continue
            self.local_scope[name] = val
        self.local_scope["_name"] = name
    
    def process_code(self, text):
        prog = [(line.strip() if COMMENT not in line else line[: line.index(COMMENT)].strip()) for line in text.split("\n")]
        for line_num, line in enumerate(prog):
            if line == "":
                prog[line_num] = tuple()
                continue
            ins, *args = line.split()
            pargs = tuple(
                map(
                    lambda x: x.strip().replace("\\\\","[¬¶-0]").replace("\\n", "\n").replace("\\t", "\t").replace("¬¶¬", ",").replace("[¬¶-0]","\\\\"),
                    " ".join(args).replace("\\,", "¬¶¬").split(",") if args else [],
                )
            )
            prog[line_num] = (ins, (*pargs,))
        return prog

    def values(self, args):
        """
        Get the values dynamically
        If a variable for example `test` and its value is 90
        you cam get it using `values` like bellow
        >>> self.global_scope
        >>> self.values(["%test"])
        [90]
        >>>
        """
        for pos, arg in enumerate(args):
            ## Constants
            if arg == ".none":
                args[pos] = 0
            elif arg == ".true":
                args[pos] = 1
            elif arg == ".false":
                args[pos] = 0
            elif arg == ".ignore":
                args[pos] = ".ignore:arg"
            ## Decleration checking
            elif arg.endswith("?") and arg[:-1].isidentifier():
                if arg[:-1] in self.local_scope:
                    args[pos] = 1
                else:
                    args[pos] = 0
            elif arg.endswith("??") and arg[:-2].isidentifier():
                if arg[:-2] in self.global_scope:
                    args[pos] = 1
                else:
                    args[pos] = 0
            ## Type checking
            elif arg.endswith(".int?") and arg[:-5].isidentifier() and arg[:-5] in self.local_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-5]], int) else 0
            elif arg.endswith(".str?") and arg[:-5].isidentifier() and arg[:-5] in self.local_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-5]], str) else 0
            elif arg.endswith(".flt?") and arg[:-5].isidentifier() and arg[:-5] in self.local_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-5]], float) else 0
            elif arg.endswith(".dict?") and arg[:-6].isidentifier() and arg[:-6] in self.local_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-6]], dict) else 0
            elif arg.endswith(".list?") and arg[:-6].isidentifier() and arg[:-6] in self.local_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-6]], tuple) else 0
            elif arg.endswith(".int??") and arg[:-6].isidentifier() and arg[:-6] in self.global_scope:
                args[pos] = 1 if isinstance(self.global_scope[arg[:-6]], int) else 0
            elif arg.endswith(".str??") and arg[:-6].isidentifier() and arg[:-6] in self.global_scope:
                args[pos] = 1 if isinstance(self.global_scope[arg[:-6]], str) else 0
            elif arg.endswith(".flt??") and arg[:-6].isidentifier() and arg[:-6] in self.global_scope:
                args[pos] = 1 if isinstance(self.global_scope[arg[:-6]], float) else 0
            elif arg.endswith(".dict??") and arg[:-7].isidentifier() and arg[:-7] in self.global_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-7]], dict) else 0
            elif arg.endswith(".list??") and arg[:-7].isidentifier() and arg[:-7] in self.global_scope:
                args[pos] = 1 if isinstance(self.local_scope[arg[:-7]], tuple) else 0
            ## dictionary interface
            elif arg.startswith("%") and arg.count("->") > 0:
                args[pos] = read(self.local_scope, arg[1:]) or self.err("[Error]: Invalid dictionary fetch: " + arg)
            elif arg.startswith("local%") and arg.count("->") > 0:
                args[pos] = read(self.local_scope, arg[6:]) or self.err("[Error]: Invalid dictionary fetch: " + arg)
            elif arg.startswith("global%") and arg.count("->") > 0:
                args[pos] = read(self.global_scope, arg[7:]) or self.err("[Error]: Invalid dictionary fetch: " + arg)
            ## Value fetching
            elif arg.startswith("%") and arg[1:] in self.local_scope:
                args[pos] = self.local_scope.get(arg[1:])
            elif arg.startswith("local%") and arg[6:] in self.local_scope:  # for readability
                args[pos] = self.local_scope.get(arg[6:])
            elif arg.startswith("global%") and arg[7:] in self.global_scope:  # for readability
                args[pos] = self.global_scope.get(arg[7:])
            ## Literals
            elif arg.count("-") <= 1 and arg.replace("-", "").isdigit():  # Integer
                args[pos] = int(arg)
            elif arg.count("-") <= 1 and arg.count(".") <= 1 and arg.replace("-", "").replace(".", "").isdigit():  # Float
                args[pos] = float(arg)
            elif arg.isidentifier():
                pass
            elif arg.startswith('"') and arg.endswith('"'):  # String
                args[pos] = arg[1:-1]
            elif arg.startswith('."') and arg.endswith('"'):  # vars from local
                arg = arg[2:-1]
                for name, value in self.local_scope.items():
                    arg = arg.replace(f".[{name}]", str(value))
                args[pos] = arg
            elif arg.startswith('!"') and arg.endswith('"'):  # vars from global
                arg = arg[2:-1]
                for name, value in self.local_scope.items():
                    arg = arg.replace(f".[{name}]", str(value))
                args[pos] = arg
            else:
                return str(arg)
        return tuple(args)

    def unimplemented(self, instruction):
        "Raise an error for unimplemented instructions."
        self.err(f"[Unimplemented Error]: The instruction you are using ({instruction}) is not fully implemented yet.\nThis instruction might be added in the future.")

    def unstable(self, instruction):
        "Raise an error for unstable instructions."
        self.err(
            f"[UNSTABLE ERROR]: THE INSTRUCTION YOU ARE USING ({instruction}) IS UNSTABLE AND MIGHT DAMAGE YOUR DEVICE.\nPLEASE BE AWARE THAT THIS INSTRUCTION IS STILL IN DEVELOPMENT.\nTHIS INSTRUCTION MIGHT BE DEPRECATED IF NECESSARY."
        )

    def deprecation(self, instruction, reimplementation=None):
        "Print a deprecation warning for instructions."
        print(f"[DEPRECATION WARNING]: The instruction you are using `{instruction}` might be removed in the future.")
        if reimplementation:
            print(f"It might get reimplemented as `{reimplementation}`")

    def valid_name(self, text):
        """
        Check if a string is a valid identifier with `.` in between.

        >>> self.valid_name("test.test")
        True
        >>> self.valid_name("1test.test")
        False
        >>> self.valid_name("test1.test")
        True
        >>> self.valid_name("test")
        True

        Works like `str.isidentifier` but names with `.` in them are still valid.
        """
        for name in text.split("."):
            if not name.isidentifier():
                return False
        return True

    def run(self, code):
        """
        Run a SimLang script.
        >>> self.run('println "Hello\\, world!"')
        Hello, world!
        """
        prog = self.process_code(code)
        global GLOBAL_CODE
        GLOBAL_CODE = code
        LINE_INDEX = len(self.lines)
        self.lines = append(self.lines, 0)
        self.current_line = self.lines[LINE_INDEX]
        ## Pre runtime instructions
        for line_num, _ in enumerate(prog):
            line = prog[line_num]
            if line == tuple():
                continue
            ins, pargs = list(line)
            args = tuple(self._values_nrt(list(pargs)))
            argc = len(args)
            if ins == "glabel" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error] Pre-runtime: Invalid name: " + args[0], True)
                self._jtable[args[0]] = line_num
        ## Program execution
        while self.current_line < len(prog) and self.current_line != float("inf"):
            line = prog[self.current_line]
            if line == tuple():
                self.current_line += 1
                continue
            ins, pargs = list(line)
            arguments = self.values(list(pargs))
            if type(arguments) == str:
                self._calls = append(self._calls, (self.current_line, ins, (None,), (*pargs,)))
                self.err(f"[Error]: Encountered invalid argument `{arguments}`.", True)
            args = tuple(arguments)
            argc = len(args)
            self._calls = append(self._calls, (self.current_line, ins, (*args,), (*pargs,)))
            if "//property.step_by_step" in code:
                print(self._calls[-1])
                input()
            if ins == "exit":
                break
            ## IO
            elif ins == "print" and argc > 0:
                print(*args, sep=", ", end="")
            elif ins == "println" and argc > 0:
                print(*args, sep=", ")
            elif ins == "input" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0],force=True)
                self.local_scope[args[0]] = input()
            ## Variables
            elif ins == "set" and argc == 2:
                if not args[0].isidentifier():
                    self.err(f"[Error]: Invalid name `{args[0]}`",force=True)
                self.local_scope[args[0]] = args[1]
            elif ins == "get_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.global_scope):
                    self.err("[Error]: Invalid name: " + args[0],force=True)
                self.local_scope[args[0]] = self.global_scope[args[0]]
            elif ins == "@get_class" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.classes):
                    self.err("[Error]: Invalid name: " + args[0],force=True)
                self.local_scope[args[0]] = self.classes[args[0]]
            elif ins == "set_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0],force=True)
                self.global_scope[args[0]] = self.local_scope[args[0]]
            elif ins == "rename" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0],force=True)
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1],force=True)
                self.local_scope[args[1]] = self.local_scope[args[0]]
                self.local_scope.pop(args[0])
            elif ins == "rename_global" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self.global_scope):
                    self.err("[Error]: Invalid name: " + args[0],force=True)
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1],force=True)
                self.global_scope[args[1]] = self.global_scope[args[0]]
                self.global_scooe.pop(args[0])
            elif ins == "delete" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope.pop(args[0])
            elif ins == "delete_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.global_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.global_scope.pop(args[0])
            ## Arithmetic operations
            elif ins == "dec" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    self.local_scope[args[0]] = self.local_scope[args[0]] - 1
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "inc" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    self.local_scope[args[0]] = self.local_scope[args[0]] + 1
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "add" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] + args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "sub" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] - args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "mul" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] * args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "div" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] / args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "fdiv" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] // args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "pow" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] ** args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "mod":
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = args[0] % args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            ## Comparisons
            elif ins == "ifeq" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = 1 if args[0] == args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "ifne" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = 1 if args[0] != args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "iflt" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = 1 if args[0] < args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "ifgt" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self.local_scope[args[2]] = 1 if args[0] > args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            ## Comparison statements
            elif ins == "if(==)" and argc > 0:
                k = True
                for pos,arg in enumerate(args):
                    k = arg == args[pos-1]
                if not k:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins in ("if(!=)","if(<>)") and argc > 0:
                k = True
                for pos,arg in enumerate(args):
                    k = arg == args[pos-1]
                if k:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if(>)" and argc == 2:
                if not args[0] > args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if(<)" and argc == 2:
                if not args[0] < args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if(>=)" and argc == 2:
                if not args[0] >= args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if(<=)" and argc == 2:
                if not args[0] <= args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if!(>)" and argc == 2:
                if args[0] > args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if!(<)" and argc == 2:
                if args[0] < args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if!(>=)" and argc == 2:
                if args[0] >= args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "if!(<=)" and argc == 2:
                if args[0] <= args[1]:
                    oldp = self.current_line
                    k = self.jumpto(prog, "else", False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog, "end")
            elif ins == "shuttle" and argc == 2:
                oldp = self.current_line
                if args[0] == args[1]:
                    k=self.jumpto(prog,"shuttle_case(==)",False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog,"end")
                elif args[0] > args[1]:
                    k=self.jumpto(prog,"shuttle_case(>)",False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog,"end")
                elif args[0] < args[1]:
                    k=self.jumpto(prog,"shuttle_case(<)",False)
                    if k == 1:
                        self.current_line = oldp
                        self.jumpto(prog,"end")
                else:
                    self.jumpto(prog,"end")
            elif ins.startswith("shuttle_case") and argc == 0:
                self.jumpto(prog,"end")
            elif ins == "else" and argc == 0:
                self.jumpto(prog, "end")
            ## Control flow
            elif ins == "label" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._jtable[args[0]] = self.current_line
            elif ins == "goto" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable) or type(self._jtable.get(args[0])) != int:
                    self.err("[Error]: Invalid name: " + args[0])
                self.current_line = self._jtable[args[0]]
            elif ins == "giz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable) or type(self._jtable.get(args[0])) != int:
                    self.err("[Error]: Invalid name: " + args[0])
                if args[1] == 0:
                    self.current_line = self._jtable[args[0]]
            elif ins == "gnz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable) or type(self._jtable.get(args[0])) != int:
                    self.err("[Error]: Invalid name: " + args[0])
                if args[1] != 0:
                    self.current_line = self._jtable[args[0]]
            elif ins == "ggz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable) or type(self._jtable.get(args[0])) != int:
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    if args[1] > 0:
                        self.current_line = self._jtable[args[0]]
                except:
                    pass
            elif ins == "glz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    if args[1] < 0:
                        self.current_line = self._jtable[args[0]]
                except:
                    pass
            ## Python Class Interface
            elif ins == "@init_class" and argc >= 2:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                c = self.local_scope[args[0]]
                if not isinstance(c,object):
                    self.err("Classes [Error]: Invalid object: "+str(args[0]))
                else:
                    self.classes[args[1]] = c(*args[2:])
            elif ins == "@delete_class" and argc == 1:
                if args[0] not in self.modules:
                    self.err("[Error]: Invalid name: " + args[0])
                self.classes.pop(args[0])
            ## Random
            elif ins == "random_choice" and argc == 2:
                if not hasattr(args[0], "__iter__"):
                    self.err("[Error]: Object must be a string, list or a dict!")
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + str(args[1]))
                self.local_scope[args[1]] = choose_random(args[0])
            elif ins == "random_int" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + str(args[1]))
                self.local_scope[args[2]] = randint(args[0], args[1])
            ## Strings
            elif ins == "length" and argc == 2:
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self.local_scope[args[1]] = len(args[0])
            elif ins == "copy" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self.local_scope[args[1]] = args[0]
            elif ins == "split" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != str:
                    (self.err("[Error]: Invalid type: " + str(type(args[0]))) + " " + ste(args[0]))
                if type(args[1]) != str:
                    (self.err("[Error]: Invalid type: " + str(type(args[1]))) + " " + str(args[1]))
                self.local_scope[args[0]] = tuple(self.local_scope[args[0]].split(args[1]))
            elif ins == "join" and argc == 2:
                if (type(self.local_scope.get(args[1])) != tuple) or args[1] not in self.local_scope:
                    self.err("[Error]: Invalid data: " + args[1])
                if type(args[0]) != str:
                    self.err("[Error]: Invalid type: " + str(type(args[0])))
                self.local_scope[args[1]] = args[0].join(self.local_scope[args[1]])
            elif ins == "string" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                oldp = self.current_line
                lines_ = []
                scode = code.split("\n")
                while self.current_line < len(prog):
                    line = prog[self.current_line][0] if len(prog[self.current_line]) > 0 else ""
                    if line == f"end:string:{args[0]}":
                        break
                    self.current_line += 1
                    lines_.append(scode[self.current_line])
                else:
                    self.current_line = oldp
                    self.err(f"[Error]: String `{args[0]}` not closed!\nUse `end:string:{args[0]}` to end the string.")
                self.local_scope[args[0]] = "\n".join(lines_[:-1])
            elif ins == "slice" and argc == 4:
                if not isinstance(args[0],(str,tuple)):
                    self.err("[Error]: Invalid data type for first argument!")
                if (not isinstance(args[1],int)) or (not isinstance(args[2],int)):
                    self.err("[Error]: Invalid data type for slices!")
                if not args[3].isidentifier():
                    self.err("[Error]: Invalid name: " + args[3])
                self.local_scope[args[3]] = args[0][args[1]:args[2]]
            elif ins == "slice_begin" and argc == 3:
                if not isinstance(args[0],(str,tuple)):
                    self.err("[Error]: Invalid data type for first argument!")
                if not isinstance(args[1],int):
                    self.err("[Error]: Invalid data type for starting index!")
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                self.local_scope[args[2]] = args[0][args[1]:]
            elif ins == "slice_end" and argc == 3:
                if not isinstance(args[0],(str,tuple)):
                    self.err("[Error]: Invalid data type for first argument!")
                if not isinstance(args[1],int):
                    self.err("[Error]: Invalid data type for ending index!")
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                self.local_scope[args[2]] = args[0][:args[1]]
            ## Functions
            elif ins == "pfunc" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._jtable[args[0]] = ("partial:func", tuple(), {})
            elif ins == "func_default_value" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._jtable:
                    self.err(f"[Error]: Invalid name `{args[0]}`.\nplease prototype the function `{args[0]}` before using the `func_default_value` instruction.")
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._jtable[args[0]][2][args[1]] = args[2]
            elif ins == "func" and argc > 0:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                oldp = self.current_line
                if args[0] not in self._jtable:
                    self._jtable[args[0]] = (self.current_line, (*args[1:],), {})
                else:
                    vals = list(self._jtable[args[0]])
                    vals[0], vals[1] = (self.current_line, (*args[1:],))
                    self._jtable[args[0]] = tuple(vals)
                while self.current_line < len(prog):
                    line = prog[self.current_line][0] if len(prog[self.current_line]) > 0 else ""
                    if line == f"end:func:{args[0]}":
                        break
                    self.current_line += 1
                else:
                    self.current_line = oldp
                    self.err(f"[Error]: Function `{args[0]}` not closed!\nUse `end:func:{args[0]}` to close the function.")
            elif ins == "return":
                if self._call_stack == tuple():
                    self.err("[Error]: Invalid return!")
                self.current_line = self._call_stack[-1]
                self._call_stack = self._call_stack[:-1]
                returns = []
                for arg in args:
                    if not (arg.isidentifier() and arg in self.local_scope):
                        self.err("[Error]: Invalid name: " + arg)
                    returns.append((arg,self.local_scope[arg]))
                self.pop_scope()
                self.local_scope.update(dict(returns))
                self._iter -= 1
            elif ins == "call" and argc > 0:
                if (not args[0].isidentifier()) or args[0] not in self._jtable or type(self._jtable.get(args[0])) != tuple:
                    self.err("[Error]: Invalid name: " + args[0])
                jump, arg_name, defs = self._jtable[args[0]]
                if jump == "partial:func":
                    self.err(f"[Error]: Function `{args[0]}` not fully defined!")
                self._call_stack = append(self._call_stack, self.current_line)
                self.new_scope()
                if self._iter > self.global_scope.get("_sys_max_recursive_calls", 10_000):
                    self.err(
                        "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz]` for loops!",
                        True,
                    )
                self.current_line = jump
                self._iter += 1
                self.local_scope.update(defs)
                for name, val in zip(arg_name, args[1:]):
                    if val == ".ignore:arg":
                        continue
                    self.local_scope[name] = val
                self.local_scope["_name"] = args[0]
            elif ins in self._jtable and type(self._jtable.get(ins, None)) == tuple:
                jump, arg_name, defs = self._jtable[ins]
                if jump == "partial:func":
                    self.err(f"[Error]: Function `{ins}` not fully defined!")
                self._call_stack = append(self._call_stack, self.current_line)
                self.new_scope()
                if self._iter > self.global_scope.get("_sys_max_recursive_calls", 10_000):
                    self.err(
                        "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz]` for loops!",
                        True,
                    )
                self.current_line = jump
                self._iter += 1
                self.local_scope.update(defs)
                if len(args) < len(arg_name) and arg_name[len(tuple(zip(arg_name, args))) :] != tuple(defs.keys()):
                    out = "Missed:\n"
                    for name in arg_name[len(tuple(zip(arg_name, args))) :]:
                        out += f" - {name}\n"
                    out = out[:-1]
                    self.err(f"[Error]: Mismatch in arguments! Function got less arguments than expected.\n{out}")
                if len(args) > len(arg_name):
                    out = "Extra:\n"
                    for name in args[len(tuple(zip(arg_name, args))) :]:
                        out += f" - {name}\n"
                    out = out[:-1]
                    self.err(f"[Error]: Mismatch in arguments! Function got more arguments than expected.\n{out}")
                for name, val in zip(arg_name, args):
                    if val == ".ignore:arg":
                        continue
                    self.local_scope[name] = val
                self.local_scope["_name"] = ins
            elif ins in self._jtable and type(self._jtable.get(ins, None)) != tuple:
                self.err(f'[Error]: Label is not callable, use `[goto/giz/gnz/glz/ggz] "{ins}"` instead.')
            ## Packaged function (unstable error)
            elif ins == "ppack" and argc == 1:
                self.unstable(ins)
            elif ins == "pack_default_value" and argc == 3:
                self.unstable(ins)
            elif ins == "pack" and argc > 0:
                self.unstable(ins)
            elif ins == "callp" and argc > 0:
                self.unstable(ins)
            elif ins.startswith("pack:") and ins[5:] in self._func and type(self._func.get(ins[5:], None)) == tuple:
                self.unstable(ins)
            ## Type casting
            elif ins == "to_int" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = int(self.local_scope[args[0]])
            elif ins == "to_str" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = str(self.local_scope[args[0]])
            elif ins == "to_flt" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = float(self.local_scope[args[0]])
            ## Errors
            elif ins == "raise_error" and argc == 1:
                self._calls = self._calls[:-1]
                self.err(args[0])
            ## Execution
            elif ins == "run_file" and argc == 1:
                self.deprecation(ins, "import")
                if not os.path.isfile(args[0]):
                    self.err("[Error]: File not found: " + args[0])
                if len(self.lines) > MAX_SCRIPT_CALLS:
                    self.err(
                        f"""[Error-Crit]: Too many scripts to handle!
Fixes:
 - Wait until a script finishes to run another script.
 - Look for recursive calls.
 - Put the code in the main script instead of using a separate one.
Causes:
 - Recursive calls (calling a script that runs it self in it self)
 - Running to many scripts, every script, everywhere all at once.
MAX_SCRIPT_CALLS: {MAX_SCRIPT_CALLS}
Error from: {args[0]}""",
                        force=True,
                    )
                self._files.append(args[0])
                self.run(open(args[0]).read())
                self.current_line = self.lines[-1]
                self.lines = self.lines[:-1]
                self.lines = append(self.lines, self.current_line)
                self._files.pop()
            ## Extensions
            elif ins == "include" and argc > 0:
                for file in args:
                    self.include(file)
            elif ins == "include_std" and argc > 0:
                for file in args:
                    self.include_std(file)
            elif ins == "has_extension" and argc == 2:
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self.local_scope[args[1]] = 1 if os.path.isfile(LIBDIR + args[0]) else 0
            elif ins == "include:module" and argc == 1:
                file = self.import_module(args[0])
                if file == None:
                    continue
                elif file.NAME == None:
                    file.NAME = "undefined"
                self.classes[file.NAME] = file
            ## System
            elif ins == "sys_console" and argc == 1:
                self.local_scope["_ret_code"] = os.system(args[0])
            ## Python Classes Fancy Interface
            elif ins.split("::")[0] in self.classes and hasattrbypath("::".join(ins.split("::")[1:]), self.classes[ins.split("::")[0]]):
                t = hasattr(
                    getattrbypath("::".join(ins.split("::")[1:]), self.classes[ins.split("::")[0]]),
                    "__call__",
                )
                if t:
                    res = getattrbypath("::".join(ins.split("::")[1:]), self.classes[ins.split("::")[0]])(*args)
                    if isinstance(res, list):
                        self.local_scope["_return"] = tuple(res)
                    elif isinstance(res, bool):
                        self.local_scope["_return"] = 1 if res else 0
                    elif res == None:
                        self.local_scope["_return"] = 0
                    else:
                        self.local_scope["_return"] = res
                else:
                    res = getattrbypath("::".join(ins.split("::")[1:]), self.classes[ins.split("::")[0]])
                    if isinstance(res, list):
                        self.local_scope["_return"] = tuple(res)
                    elif isinstance(res, bool):
                        self.local_scope["_return"] = 1 if res else 0
                    elif res == None:
                        self.local_scope["_return"] = 0
                    else:
                        self.local_scope["_return"] = res
            ## Lists
            elif ins == "list_new" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = tuple()
            elif ins == "list_init" and argc == 1:
                lines_ = []
                scode = code.split("\n")
                oldp = self.current_line
                while self.current_line < len(prog):
                    line = prog[self.current_line][0] if len(prog[self.current_line]) > 0 else ""
                    if line == f"end:list:{args[0]}":
                        break
                    line = scode[self.current_line]
                    lines_.append(line.strip() if COMMENT not in line else line[: line.index(COMMENT)].strip())
                    self.current_line += 1
                else:
                    self.current_line = oldp
                    self.err(f"[Error]: List `{args[0]}` not closed!\nUse `end:list:{args[0]}` to close the list.")
                self.local_scope[args[0]] = self.values(lines_[1:])
            elif ins == "list_make" and argc == 2:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = tuple([0] * args[1])
            elif ins == "list_make" and argc == 3:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = tuple([args[2]] * args[1])
            elif ins == "list_append" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                self.local_scope[args[0]] = tuple([*self.local_scope[args[0]], args[1]])
            elif ins == "list_pop" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                self.local_scope[args[1]] = self.local_scope[args[0]][-1] if self.local_scope[args[0]] else -1
                if [*self.local_scope[args[0]]]:
                    self.local_scope[args[0]] = tuple(self.local_scope[args[0]][:-1])
            elif ins == "list_reverse" and argc == 1:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                self.local_scope[args[0]] = self.local_scope[args[0]][::-1]
            elif ins == "list_assign" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                if not isinstance(args[1], int):
                    self.err("[Error]: Invalid type for an index!")
                self.local_scope[args[0]][args[1]] = args[2]
            elif ins == "list_get" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                if not isinstance(args[1], int):
                    self.err("[Error]: Invalid type for an index!")
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                self.local_scope[args[2]] = self.local_scope[args[0]][args[1]]
            ## Dictionaries
            elif ins == "dictionary_new" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = {}
            elif ins == "dictionary_add_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != dict:
                    self.err("[Error]: Invalid data type! Variable is not a dictionary: " + str(args[2]))
                if id(self.local_scope[args[0]]) == id(args[2]) and type(args[2]) == dict:
                    self.local_scope[args[0]][args[1]] = args[2].copy()
                else:
                    self.local_scope[args[0]][args[1]] = args[2]
            elif ins == "strict_dictionary_add_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != dict:
                    self.err("[Error]: Invalid data type! Variable is not a dictionary!: " + str(args[2]))
                self.local_scope[args[0]][args[1]] = args[2]
            elif ins == "dictionary_get_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != dict:
                    self.err("[Error]: Invalid data type")
                self.local_scope[args[2]] = self.local_scope[args[0]].get(args[1], 0)
            elif ins == "dictionary_pop_item" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != dict:
                    self.err("[Error]: Invalid data type!")
                self.local_scope[args[0]].pop(args[1], 0)
            ## File IO
            elif ins == "read_file" and argc == 2:
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                if not os.path.isfile(args[0]):
                    self.err("[Error]: Invalid file: " + args[0])
                self.local_scope[args[1]] = open(args[0]).read()
            elif ins == "write_file" and argc == 2:
                open(args[0], "w").write(str(args[1]))
            elif ins == "append_file" and argc == 2:
                open(args[0], "a").write(str(args[1]))
            ## File operations
            elif ins == "isfile" and argc == 2:
                if not args[1].isidentifier():
                    self.err(f"[Error]: Invalid name: {args[1]}")
                self.local_scope[args[1]] = 1 if os.path.isfile(args[0]) else 0
            elif ins == "isdir" and argc == 2:
                if not args[1].isidentifier():
                    self.err(f"[Error]: Invalid name: {args[1]}")
                self.local_scope[args[1]] = 1 if os.path.isdir(args[0]) else 0
            elif ins == "makedir" and argc == 1:
                try:
                    os.makedirs(args[0], exist_ok=True)
                except Exception as e:
                    self.err(f"[Error]: {str(e)}")
            elif ins == "rmdir" and argc == 1:
                try:
                    shutil.rmtree(args[0])
                except Exception as e:
                    self.err(f"[Error]: {str(e)}")
            elif ins == "rmfile" and argc == 1:
                try:
                    os.remove(args[0])
                except Exception as e:
                    self.err(f"[Error]: {str(e)}")
            ## Pass
            elif ins in self._ignore:
                pass
            ## Scopes
            elif ins == "[[" and argc == 0:
                self.new_scope()
            elif ins == "]]" and argc == 0:
                self.pop_scope()
            elif ins == "locs":
                print(self.local_scope)
            elif ins == "unclutter":
                for var in self.local_scope.copy():
                    if var.startswith("_"):
                        self.local_scope.pop(var)
            else:
                self.err("[Error]: Invalid instruction: " + ins)
            self.current_line += 1 if type(self.current_line) == int else sys.exit()
            self.lines = list(self.lines)
            self.lines[LINE_INDEX] = self.current_line
            self.lines = tuple(self.lines)
        self.current_line = self.lines[-1]
        if len(self.lines) == 1:
            self.current_line = float("inf")
            return
        self.lines = self.lines[:-1]

    def err(self, msg="", force=False):
        """
        Print the call stack and print the error.
        """
        MAX_CALLS = 50
        if self._calls:
            print("======== [ Error ] =======\nExplicit is better than implicit.")
            print("Most recent call last:")
            for pos, [line, ins, args, pargs] in enumerate(self._calls):
                if len(self._calls) > MAX_CALLS and len(compress(self._calls)) < MAX_CALLS:
                    print(f"Estimated {len(self._calls)*3:,}~ Lines of error output...\nThis is not the entire call list. This is just a sub set.")
                    for pos, [line, ins, args, pargs] in enumerate(compress(self._calls)):
                        if ins not in self._mods:
                            if args != tuple() and pargs != tuple():
                                print(
                                    f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}{" - function" if ins in self._jtable and type(self._jtable.get(ins)) == tuple else ""}\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}'
                                )
                            else:
                                print(
                                    f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}{" - function" if ins in self._jtable and type(self._jtable.get(ins)) == tuple else ""}\n      No arguments'
                                )
                            if ins in self._jtable and type(self._jtable.get(ins)) == tuple:
                                print(
                                    "      Function parameters:",
                                    self._jtable.get(ins)[1],
                                )
                        elif ins in self._mods:
                            if args != tuple() and pargs != tuple():
                                print(f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}")
                            else:
                                print(f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n      No arguments")
                    break
                elif len(self._calls) > MAX_CALLS and len(compress(self._calls)) > MAX_CALLS:
                    print(
                        f"CALL STACK TOO LARGE TO DISPLAY EVEN WHEN COMPRESSED!\nFull length of the call stack {len(self._calls):,} and total lines of output {len(self._calls)*3:,}~.\nWhen compressed {len(compress(self._calls)):,} and total lines of output {len(compress(self._calls))*3:,}~."
                    )
                    break
                if ins not in self._mods:
                    if args != tuple() and pargs != tuple():
                        print(
                            f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}{" - function" if ins in self._jtable and type(self._jtable.get(ins)) == tuple else ""}\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}'
                        )
                    else:
                        print(
                            f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}{" - function" if ins in self._jtable and type(self._jtable.get(ins)) == tuple else ""}\n      No arguments'
                        )
                        if ins in self._jtable and type(self._jtable.get(ins)) == tuple:
                            print("      Function parameters:", self._jtable.get(ins)[1])
                elif ins in self._mods:
                    if args != tuple() and pargs != tuple():
                        print(f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}")
                    else:
                        print(f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n      No arguments")
        print(
            "\n====== [ Details ] ======\n"
            + msg
            + f"\nError found at line {(self.current_line+1 if type(self.current_line) == int else '[OutOfBounds]')}\nIn file `{self._files[-1] if self._files else '[OutOfBounds]'}`"
        )
        try:
            print(f"This line -> `{GLOBAL_CODE.split(chr(10))[self.current_line]}`\n")
        except IndexError:
            print("Failed to get line.\n")
        except TypeError:
            print("Failed to get line.\n")
        if force == True:
            print("wtf")
            sys.exit()
        else:
            self.exit()

    def exit(self):
        """
        Default exit method.
        """
        self.current_line = float("inf")

    def set_exit_method(self, function):
        """
        Used by repr only!
        """
        self._exit_method = function
   
    def rm_exit_method(self):
        """
        Used by repr only!
        """
        self._exit_method = lambda: None 