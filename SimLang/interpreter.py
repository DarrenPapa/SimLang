# I used black with --fast and --safe to format the code (some of it)
import os
import sys
import traceback
import shutil
from random import choice as choose_random
from random import randint

## Handle local dir and where to put libs folder
os.chdir(os.getcwd())
LOCALDIR = os.getcwd() + "/"
del sys.path[0]
sys.path[0] = LOCALDIR
if os.name == "nt":
    HOST_OS = sys.platform
    LIBDIR = os.path.join(os.getenv("APPDATA"),"simlang_libs")+"\\"
elif os.name == "posix":
    HOST_OS = sys.platform
    LIBDIR = "~/simlang_libs/"
else:
    HOST_OS = "Unknown"
    LIBDIR = "./dependencies/"
HOST_OS = HOST_OS.title()
LIBDIR = os.path.expanduser(LIBDIR)

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
    '''A class to encapsulate modules.'''
    def __init__(self,module):
        self.__module = module
        self.__call_to_lock()
    def Mreplace_module(self,module):
        if self.__module == module:
            raise Exception("Module cannot be the same!")
        self.__module = module
    @property
    def Mmodule(self):
        return self.__module
    def __call_to_lock(self):
        def setattr(self,name,value):
            raise Exception("Module Capsule object is read only!")
        self.__setattr__ = setattr
    def __getattr__(self,other):
        return getattr(self.__module,other) if hasattr(self.__module,other) else (getattr(self,other) if hasattr(self,other) else None)
    def __repr__(self):
        return f"<Module Capsule for '{self.__module.__name__}' in '{self.__module.__file__}'>"

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

def getattrbypath(path,obj,sep="::"):
    if len(path.split(sep)) == 1:
        return getattr(obj,path)
    return getattrbypath(sep.join(path.split(sep)[1:]),getattr(obj,path.split(sep)[0]),sep)

def hasattrbypath(path,obj,sep="::"):
    if len(path.split(sep)) == 1:
        return hasattr(obj,path)
    return getattrbypath(sep.join(path.split(sep)[1:]),getattr(obj,path.split(sep)[0]),sep)

def getfilename(path):
    name = os.path.basename(path).split(".")[::-1][-1]
    return name

def compress(items):
    l = tuple()
    for item in items:
        if item not in l:
            l = tuple([*l, item])
    return l

def append(tup:tuple,item) -> tuple:
    k = list(tup);k.append(item)
    return tuple(k)

def pop(tup:tuple):
    k = list(tup)
    return k.pop() if k else None

class inter_class:
    __slots__ = tuple(
        "_csgui _exit_method modules current_line _default_scope _files _func _scope global_scope local_scope _jtable _mods _call_stack _calls data _ignore _iter _ns lines".split()
    )

    def __init__(self,path,name="script:main"):
        self._exit_method = self.exit
        self._csgui = self.csgui
        self._default_scope = {
            "_sys_host_os_name": os.name,
            "_sys_libdir": LIBDIR,
            "_sys_localdir": LOCALDIR,
            "_lib_OS": os,
            "_lib_SYS": sys,
            "_md_file": path,
            "_sys_scope_depth": 0
        }
        self._scope = [self._default_scope.copy()]
        self.global_scope = self._scope[0]
        self.global_scope["_sys_max_recursive_calls"] = 10_000  # max calls without returning 
        self.local_scope = self._scope[-1]
        self.modules = {
          'os':os,
          'sys':sys
        }
        self._jtable = {}
        self._mods = {}
        self._call_stack = tuple()
        self._calls = tuple()
        self.data = data_node()
        self._ignore = ["glabel"]
        self._iter = 0
        self._ns = None
        self.lines = tuple()
        self._files = [name]
        self._func = {}

    def is_func(self,name):
        if type(name) != str:
            self.err(f"[Error]: Invalid type for name!")
        elif not name.isidentifier():
            self.err(f"[Error]: Invalid name `{name}`")
        if name not in self._jtable or type(self._jtable.get(name)) != tuple:
            return False
        elif name in self._jtable and type(self._jtable.get(name)) == tuple:
            return True
        return False
    
    def is_label(self,name):
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
                else self.err(
                    func.__doc__
                    if func.__doc__
                    else f"[Error-Mod]: Miss matching arguments.\nExpected {args} but recieved {len(x)}."
                ), True
            )
            return func
        return wrapper

    def iadd_mod(self, args):
        def wrapper(func):
            self._mods[f"{self._ns}.{func.__name__}" if self._ns != None else func.__name__] = (
                lambda *x: func(self, *x)
                if ((len(x) == args) if args != -1 else (len(x) > 0))
                else self.err(
                    func.__doc__
                    if func.__doc__
                    else f"[Error-Mod]: Miss matching arguments.\nExpected {args} but recieved {len(x)}."
                )
            )
            return func
        return wrapper

    def include(self, path):
        mod = {"inter": self, "__file__": LOCALDIR + "/" + path, "sys_host_os": os.name}
        self._ns = getfilename(path)
        if not os.path.isfile(LOCALDIR + path):
            self.err(
                f'[Error]: "{LOCALDIR+path}" is not an extension.\nIt wasn\'t found in the local directory!'
                + (
                    f'\nDid you mean `include_std "{path}"`?\n"{path}" Was found in the libs directory.'
                    if os.path.isfile(LIBDIR + path)
                    else ""
                ), force = True
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
                + (
                    f'\nDid you mean `include "{path}"`?\n"{path}" Was found in the local directory.'
                    if os.path.isfile(LOCALDIR + path)
                    else ""
                ), force = True
            )
        try:
            exec(compile(open(LIBDIR + path).read(), path, "exec"), mod)
        except:
            self.err(traceback.format_exc())
        self._ignore.extend(mod.get("_sys_ignore", []))
        self._ns = None

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
            elif (
                arg.count("-") <= 1
                and arg.count(".") <= 1
                and arg.replace("-", "").replace(".", "").isdigit()
            ):  # Float
                args[pos] = float(arg)
            elif arg.isidentifier():
                pass
            elif arg.startswith('"') and arg.endswith('"'):
                args[pos] = arg[1:-1]
        return tuple(args)

    def values(self, args):
        '''
        Get the values dynamically
        If a variable for example `test` and its value is 90
        you cam get it using `values` like bellow
        >>> self.global_scope
        >>> self.values(["%test"])
        [90]
        >>> 
        '''
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
            elif (
                arg.endswith(".int?")
                and arg[:-5].isidentifier()
                and arg[:-5] in self.local_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-5]],int) else 0
            elif (
                arg.endswith(".str?")
                and arg[:-5].isidentifier()
                and arg[:-5] in self.local_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-5]],str) else 0
            elif (
                arg.endswith(".flt?")
                and arg[:-5].isidentifier()
                and arg[:-5] in self.local_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-5]],float) else 0
            elif (
                arg.endswith(".dict?")
                and arg[:-6].isidentifier()
                and arg[:-6] in self.local_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-6]],dict) else 0
            elif (
                arg.endswith(".list?")
                and arg[:-6].isidentifier()
                and arg[:-6] in self.local_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-6]],tuple) else 0
            elif (
                arg.endswith(".int??")
                and arg[:-6].isidentifier()
                and arg[:-6] in self.global_scope
            ):
                args[pos] = 1 if isinstance(self.global_scope[arg[:-6]],int) else 0
            elif (
                arg.endswith(".str??")
                and arg[:-6].isidentifier()
                and arg[:-6] in self.global_scope
            ):
                args[pos] = 1 if isinstance(self.global_scope[arg[:-6]],str) else 0
            elif (
                arg.endswith(".flt??")
                and arg[:-6].isidentifier()
                and arg[:-6] in self.global_scope
            ):
                args[pos] = 1 if isinstance(self.global_scope[arg[:-6]],float) else 0
            elif (
                arg.endswith(".dict??")
                and arg[:-7].isidentifier()
                and arg[:-7] in self.global_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-7]],dict) else 0
            elif (
                arg.endswith(".list??")
                and arg[:-7].isidentifier()
                and arg[:-7] in self.global_scope
            ):
                args[pos] = 1 if isinstance(self.local_scope[arg[:-7]],tuple) else 0
            ## dictionary interface
            elif arg.startswith("%") and arg.count("->") > 0:
                args[pos] = read(self.local_scope, arg[1:]) or self.err(
                    "[Error]: Invalid dictionary fetch: " + arg
                )
            elif arg.startswith("local%") and arg.count("->") > 0:
                args[pos] = read(self.local_scope, arg[6:]) or self.err(
                    "[Error]: Invalid dictionary fetch: " + arg
                )
            elif arg.startswith("global%") and arg.count("->") > 0:
                args[pos] = read(self.global_scope, arg[7:]) or self.err(
                    "[Error]: Invalid dictionary fetch: " + arg
                )
            ## Value fetching
            elif arg.startswith("%") and arg[1:] in self.local_scope:
                args[pos] = self.local_scope.get(arg[1:])
            elif arg.startswith("local%") and arg[6:] in self.local_scope:  # for readability
                args[pos] = self.local_scope.get(arg[6:])
            elif (
                arg.startswith("global%") and arg[7:] in self.global_scope
            ):  # for readability
                args[pos] = self.global_scope.get(arg[7:])
            ## Literals
            elif arg.count("-") <= 1 and arg.replace("-", "").isdigit():  # Integer
                args[pos] = int(arg)
            elif (
                arg.count("-") <= 1
                and arg.count(".") <= 1
                and arg.replace("-", "").replace(".", "").isdigit()
            ):  # Float
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

    def unimplemented(self,instruction):
        'Raise an error for unimplemented instructions.'
        self.err(f"[Unimplemented Error]: The instruction you are using ({instruction}) is not fully implemented yet.\nThis instruction might be added in the future.")

    def unstable(self,instruction):
        'Raise an error for unstable instructions.'
        self.err(f"[UNSTABLE ERROR]: THE INSTRUCTION YOU ARE USING ({instruction}) IS UNSTABLE AND MIGHT DAMAGE YOUR DEVICE.\nPLEASE BE AWARE THAT THIS INSTRUCTION IS STILL IN DEVELOPMENT.\nTHIS INSTRUCTION MIGHT BE DEPRECATED IF NECESSARY.")

    def deprecation(self,instruction,reimplementation=None):
        'Print a deprecation warning for instructions.'
        print(f"[DEPRECATION WARNING]: The instruction you are using `{instruction}` might be removed in the future.")
        if reimplementation:
            print(f"It might get reimplemented as `{reimplementation}`")

    def valid_name(self, text):
        '''
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
        '''
        for name in text.split('.'):
            if not name.isidentifier():
                return False
        return True

    def run(self, code):
        prog = [
            (
                line.strip()
                if COMMENT not in line
                else line[: line.index(COMMENT)].strip()
            )
            for line in code.split("\n")
        ]
        global GLOBAL_CODE
        GLOBAL_CODE = code
        LINE_INDEX = len(self.lines)
        self.lines = append(self.lines,0)
        self.current_line = self.lines[LINE_INDEX]
        ## Program processing
        for line_num, line in enumerate(prog):
            if line == "":
                prog[line_num] = tuple()
                continue
            ins, *args = line.split()
            pargs = tuple(
                map(
                    lambda x: x.strip()
                    .replace("\\n", "\n")
                    .replace("\\t", "\t")
                    .replace("¬¶¬", ","),
                    " ".join(args).replace("\\,", "¬¶¬").split(",") if args else [],
                )
            )
            prog[line_num] = (ins, (*pargs,))
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
                    self.err("[Error] Pre-runtime: Invalid name: " + args[0],True)
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
                self.err(f"[Error]: Encountered invalid argument `{arguments}`.",True)
            args = tuple(arguments)
            argc = len(args)
            self._calls = append(self._calls, (self.current_line, ins, (*args,), (*pargs,)))
            if "//property.step_by_step" in code:
                print(self._calls[-1])
                input()
            if ins == "exit":
                break
            ## IO
            elif ins == "print" and argc == 1:
                print(args[0], end="")
            elif ins == "println" and argc == 1:
                print(args[0])
            elif ins == "input" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = input()
            ## Variables
            elif ins == "set" and argc == 2:
                if not args[0].isidentifier():
                    self.err(f"[Error]: Invalid name `{args[0]}`")
                self.local_scope[args[0]] = args[1]
            elif ins == "to_const" and argc == 1:
                if not args[0].isidentifier():
                    self.err(f"[Error]: Invalid name `{args[0]}`")
            elif ins == "get_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.global_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.local_scope[args[0]] = self.global_scope[args[0]]
            elif ins == "set_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                self.global_scope[args[0]] = self.local_scope[args[0]]
            elif ins == "rename" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self.local_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self.local_scope[args[1]] = self.local_scope[args[0]]
                self.local_scope.pop(args[0])
            elif ins == "rename_global" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self.global_scope):
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
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
            ## Control flow
            elif ins == "label" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._jtable[args[0]] = self.current_line
            elif ins == "goto" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                self.current_line = self._jtable[args[0]]
            elif ins == "giz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                if args[1] == 0:
                    self.current_line = self._jtable[args[0]]
            elif ins == "gnz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                if args[1] != 0:
                    self.current_line = self._jtable[args[0]]
            elif ins == "ggz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
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
            ## Random
            elif ins == "random_choice" and argc == 2:
                if not hasattr(args[0], "__iter__"):
                    self.err("[Error]: Object must be a string, list or a dict!")
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + str(args[1]))
                self.local_scope[args[1]] = choice_random(args[0])
            elif ins == "random_int" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + str(args[1]))
                self.local_scope[args[2]] = randint(args[0],args[1])
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
                    self.err("[Error]: Invalid type: " + str(type(args[0]))) + " " + ste(args[0])
                if type(args[1]) != str:
                    self.err("[Error]: Invalid type: " + str(type(args[1]))) + " " + str(args[1])
                self.local_scope[args[0]] = tuple(self.local_scope[args[0]].split(args[1]))
            elif ins == "join" and argc == 2:
                if (type(self.local_scope.get(args[1])) != tuple) or args[
                    1
                ] not in self.local_scope:
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
                    vals[0], vals[1] = (self.current_line,(*args[1:],))
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
                for arg in args:
                    if not (arg.isidentifier() and arg in self.local_scope):
                        self.err("[Error]: Invalid name: " + arg)
                    self.global_scope[arg] = self.local_scope[arg]
                self.pop_scope()
                self._iter -= 1
            elif ins == "call" and argc > 0:
                if (not args[0].isidentifier()) or args[0] not in self._jtable or type(self._jtable.get(args[0])) != tuple:
                    self.err("[Error]: Invalid name: " + args[0])
                jump, arg_name, defs = self._jtable[args[0]]
                if jump == "partial:func":
                    self.err(f"[Error]: Function `{args[0]}` not fully defined!")
                self._call_stack = append(self._call_stack,self.current_line)
                self.new_scope()
                if self._iter > self.global_scope.get("_sys_max_recursive_calls", 10_000):
                    self.err(
                        "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz]` for loops!", True
                    )
                self.current_line = jump
                self._iter += 1
                self.local_scope.update(defs)
                for name, val in zip(arg_name, args[1:]):
                    if val == ".ignore:arg":
                        continue
                    self.local_scope[name] = val
                self.local_scope["_name"] = args[0]
            elif ins == "locs":
                print(self.local_scope)
            elif ins in self._jtable and type(self._jtable.get(ins, None)) == tuple:
                jump, arg_name, defs = self._jtable[ins]
                if jump == "partial:func":
                    self.err(f"[Error]: Function `{ins}` not fully defined!")
                self._call_stack = append(self._call_stack,self.current_line)
                self.new_scope()
                if self._iter > self.global_scope.get("_sys_max_recursive_calls", 10_000):
                    self.err(
                        "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz]` for loops!", True
                    )
                self.current_line = jump
                self._iter += 1
                self.local_scope.update(defs)
                if len(args) < len(arg_name) and arg_name[len(tuple(zip(arg_name,args))):] != tuple(defs.keys()):
                    out = "Missed:\n"
                    for name in arg_name[len(tuple(zip(arg_name,args))):]:
                        out += f" - {name}\n"
                    out = out[:-1]
                    self.err(f"[Error]: Mismatch in arguments! Function got less arguments than expected.\n{out}")
                if len(args) > len(arg_name):
                    out = "Extra:\n"
                    for name in args[len(tuple(zip(arg_name,args))):]:
                        out += f" - {name}\n"
                    out = out[:-1]
                    self.err(f"[Error]: Mismatch in arguments! Function got more arguments than expected.\n{out}")
                for name, val in zip(arg_name, args):
                    if val == ".ignore:arg":
                        continue
                    self.local_scope[name] = val
                self.local_scope["_name"] = ins
            elif (
                ins in self._jtable
                and type(self._jtable.get(ins, None)) != tuple
            ):
                self.err(
                    f'[Error]: Label is not callable, use `[goto/giz/gnz/glz/ggz] "{ins}"` instead.'
                )
            ## Packaged function (unstable error)
            elif ins == "ppack" and argc == 1:
                self.unstable(ins)
            elif ins == "pack_default_value" and argc == 3:
                self.unstable(ins)
            elif ins == "pack" and argc > 0:
                self.unstable(ins)
            elif ins == "callp" and argc > 0:
                self.unstable(ins)
            elif ins.startswith('pack:') and ins[5:] in self._func and type(self._func.get(ins[5:], None)) == tuple:
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
                self.deprecation(ins,'import')
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
Error from: {args[0]}""", force = True
                    )
                self._files.append(args[0])
                self.run(open(args[0]).read())
                self.current_line = self.lines[-1]
                self.lines = self.lines[:-1]
                self.lines = append(self.lines,self.current_line)
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
            elif ins in self._mods and self.valid_name(ins):
                self._mods[ins](*args)
            ## System
            elif ins == "sys_console" and argc == 1:
                self.local_scope["_ret_code"] = os.system(args[0])
            ## Module
            elif ins.split('::')[0] in self.modules and hasattrbypath('::'.join(ins.split('::')[1:]),self.modules[ins.split('::')[0]]):
                t = hasattr(getattrbypath('::'.join(ins.split('::')[1:]),self.modules[ins.split('::')[0]]),"__call__")
                if t:
                    res = getattrbypath('::'.join(ins.split('::')[1:]),self.modules[ins.split('::')[0]])(*args)
                    if isinstance(res,list):
                        self.local_scope["_return"] = tuple(res)
                    else:
                        self.local_scope["_return"] = res
                else:
                    res = getattrbypath('::'.join(ins.split('::')[1:]),self.modules[ins.split('::')[0]])
                    if isinstance(res,list):
                        self.local_scope["_return"] = tuple(res)
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
                    lines_.append(
                        line.strip()
                        if COMMENT not in line
                        else line[:line.index(COMMENT)].strip()
                    )
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
                self.local_scope[args[1]] = (
                    self.local_scope[args[0]][-1] if self.local_scope[args[0]] else -1
                )
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
                    self.err(
                        "[Error]: Invalid data type! Variable is not a dictionary: "
                        + str(args[2])
                    )
                if id(self.local_scope[args[0]]) == id(args[2]) and type(args[2]) == dict:
                    self.local_scope[args[0]][args[1]] = args[2].copy()
                else:
                    self.local_scope[args[0]][args[1]] = args[2]
            elif ins == "strict_dictionary_add_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self.local_scope:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self.local_scope[args[0]]) != dict:
                    self.err(
                        "[Error]: Invalid data type! Variable is not a dictionary!: "
                        + str(args[2])
                    )
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
                    os.makedirs(args[0],exist_ok=True)
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
        if self._calls:
            print("======== [ Error ] =======")
            print("Most recent call last:")
            for pos, [line, ins, args, pargs] in enumerate(self._calls):
                if len(self._calls) > 50 and len(compress(self._calls)) < 50:
                    print(
                        f"Estimated {len(self._calls)*3:,}~ Lines of error output...\nThis is not the entire call list. This is just a sub set."
                    )
                    for pos, [line, ins, args, pargs] in enumerate(
                        compress(self._calls)
                    ):
                        if ins not in self._mods:
                            if args != tuple() and pargs != tuple():
                                print(
                                    f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}{" - function" if ins in self._jtable and type(self._jtable.get(ins)) == tuple else ""}\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}'
                                )
                            else:
                                print(
                                    f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}{" - function" if ins in self._jtable and type(self._jtable.get(ins)) == tuple else ""}\n      No arguments'
                                )
                            if (
                                ins in self._jtable
                                and type(self._jtable.get(ins)) == tuple
                            ):
                                print(
                                    "      Function parameters:", self._jtable.get(ins)[1]
                                )
                        elif ins in self._mods:
                            if args != tuple() and pargs != tuple():
                                print(
                                    f'Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}'
                                )
                            else:
                                print(
                                    f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n      No arguments"
                                )
                    break
                elif len(self._calls) > 50 and len(compress(self._calls)) > 50:
                    print(f"CALL STACK TOO LARGE TO DISPLAY EVEN WHEN COMPRESSED!\nFull length of the call stack {len(self._calls):,} and total lines of output {len(self._calls)*3:,}~.\nWhen compressed {len(compress(self._calls)):,} and total lines of output {len(compress(self._calls))*3:,}~.")
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
                        if (
                            ins in self._jtable
                            and type(self._jtable.get(ins)) == tuple
                        ):
                            print(
                                "      Function parameters:", self._jtable.get(ins)[1]
                            )
                elif ins in self._mods:
                    if args != tuple() and pargs != tuple():
                        print(
                            f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}"
                        )
                    else:
                        print(
                            f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n      No arguments"
                        )
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
        self.current_line = float("inf") if force == False else sys.exit()

    def csgui(self):
        self.current_line = float("inf")
        print("Call Stack GUI (enter help for more details, exit to stop)")
        while True:
            act = input("] ")
            if act == "exit":
                break
            elif act == "help":
                print(
                    """The CS GUI is a debugging tool used for programs that are 40+ lines of code where
the call stack is cluttered.

look - look for a specific line.
sect - look for an entire section.
exit - stop.

Note:
    This is not a practical programming language.
  If you are a beginner I urge you to learn Python, C, C++ or Java instead.
  This programming language's syntax is unconventional.
  Which could hinder your learning in other programming languages."""
                )
            elif act == "look":
                while True:
                    num = input(f"Instruction number (0-{len(self._calls)-1:,}) ] ")
                    if not num:
                        break
                    if not num.isdigit():
                        print("Invalid input, must be a number.")
                        continue
                    if int(num) not in range(len(self._calls)):
                        print("Invalid instruction number.")
                        continue
                    line, ins, args, pargs = self._calls[int(num)]
                    print(
                        f"Line: {line+1}\nInstruction: {ins}\nArguments: {pargs}\nProcessed arguments: {args}\nMod: {ins in self._mods}\nFunction: {ins in self._jtable and type(self._jtable.get(ins)) == tuple}"
                    )
                    if ins in self._jtable and type(self._jtable.get(ins)) == tuple:
                        print("Function arguments:", self._jtable.get(ins)[1])
                    break
            elif act == "sect":
                while True:
                    num = input(
                        f"Starting instruction number (0-{len(self._calls)-1:,}) ] "
                    )
                    if not num:
                        break
                    num1 = input(
                        f"Ending instruction number (0-{len(self._calls)-1:,} ] "
                    )
                    if not num.isdigit():
                        print("Invalid input, must be a number.")
                        continue
                    if int(num1) not in range(0, len(self._calls)):
                        print("Invalid starting instruction number.")
                        continue
                    if not num1.isdigit():
                        print("Invalid input, must be a number.")
                        continue
                    if int(num1) not in range(0, len(self._calls)):
                        print("Invalid instruction number.")
                        continue
                    start, end = int(num), int(num1)
                    for pos, [line, ins, args, pargs] in enumerate(
                        self._calls[start:end]
                    ):
                        if len(self._calls) > 100 and len(compress(self._calls)) > 100:
                            print(
                                f"Estimated {len(self._calls)*3:,}~ Lines of error output...\nDid not print call back."
                            )
                            break
                        if ins not in self._mods:
                            if args != tuple() and pargs != tuple():
                                print(
                                    f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}"
                                )
                            else:
                                print(
                                    f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins}\n      No arguments"
                                )
                        elif ins in self._mods:
                            if args != tuple() and pargs != tuple():
                                print(
                                    f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n   Unprocessed arguments: {pargs}\n   Processed arguments: {args}"
                                )
                            else:
                                print(
                                    f"Instruction [{str(pos).zfill(6)}] at line [{str(line+1).zfill(6)}]: {ins} - CUSTOM\n      No arguments"
                                )
                    break
        self.current_line = float("inf")

    def exit(self):
        self.current_line = float("inf")

    def set_exit_method(self, function):
        self._exit_method = function

    def remove_csgui(self):
        self._csgui = lambda: None
