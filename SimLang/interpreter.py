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

def read(tree, path):
    fpath = path.split("->")
    if len(fpath) != 1:
        if fpath[0] in tree:
            if type(tree[fpath[0]]) != dict:
                return 0
            return read(tree[fpath[0]], "->".join(fpath[1:]))
    else:
        return tree[fpath[0]] if fpath[0] in tree else 0


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


def getfilename(path):
    name = os.path.basename(path).split(".")[::-1][-1]
    return name


def compress(items):
    l = tuple()
    for item in items:
        if item not in l:
            l = tuple([*l, item])
    return l

class inter_class:
    __slots__ = tuple(
        "_csgui _exit_method p _default_scope _files _func _scope _global _vars _jtable _mods _call_stack _calls data _ignore _iter _ns lines atexit".split()
    )

    def __init__(self,name="main:script"):
        self._exit_method = self.exit
        self._csgui = self.csgui
        self._default_scope = {
            "_sys_host_os_name": os.name,
            "_sys_host_os": HOST_OS,
            "_sys_libdir": LIBDIR,
            "_sys_locals": LOCALDIR,
            "_lib_OS": os,
            "_lib_SYS": sys,
            "_sys_scope_depth": 0,
        }
        glob = self._default_scope.copy()
        glob["sys_max_iter"] = 10_000  # max calls without returning
        self._scope = [glob]
        self._global = self._scope[0]
        self._vars = self._scope[-1]
        self._jtable = {}
        self._mods = {}
        self._call_stack = []
        self._calls = []
        self.data = data_node()
        self._ignore = "glabel close".split()
        self._iter = 0
        self._ns = None
        self.lines = []
        self.atexit = ""
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
        self._vars = self._scope[-1]
        self._vars["_sys_scope_depth"] = len(self._scope) - 1

    def pop_scope(self):
        if len(self._scope) > 1:
            self._scope.pop()
            self._vars = self._scope[-1]
        else:
            self.err("[Error-Crit]: Cannot pop global scope!")

    def add_mod(self, name, args):
        def wrapper(func):
            self._mods[f"{self._ns}-{name}" if self._ns != None else name] = (
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
                )
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
                )
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

    def _values(self, args):
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
                if arg[:-1] in self._vars:
                    args[pos] = 1
                else:
                    args[pos] = 0
            elif arg.endswith("??") and arg[:-2].isidentifier():
                if arg[:-2] in self._global:
                    args[pos] = 1
                else:
                    args[pos] = 0
            ## Type checking
            elif (
                arg.endswith(".int?")
                and arg[:-5].isidentifier()
                and arg[:-5] in self._vars
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-5]],int) else 0
            elif (
                arg.endswith(".str?")
                and arg[:-5].isidentifier()
                and arg[:-5] in self._vars
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-5]],str) else 0
            elif (
                arg.endswith(".flt?")
                and arg[:-5].isidentifier()
                and arg[:-5] in self._vars
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-5]],float) else 0
            elif (
                arg.endswith(".dict?")
                and arg[:-6].isidentifier()
                and arg[:-6] in self._vars
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-6]],dict) else 0
            elif (
                arg.endswith(".list?")
                and arg[:-6].isidentifier()
                and arg[:-6] in self._vars
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-6]],tuple) else 0
            elif (
                arg.endswith(".int??")
                and arg[:-6].isidentifier()
                and arg[:-6] in self._global
            ):
                args[pos] = 1 if isinstance(self._global[arg[:-6]],int) else 0
            elif (
                arg.endswith(".str??")
                and arg[:-6].isidentifier()
                and arg[:-6] in self._global
            ):
                args[pos] = 1 if isinstance(self._global[arg[:-6]],str) else 0
            elif (
                arg.endswith(".flt??")
                and arg[:-6].isidentifier()
                and arg[:-6] in self._global
            ):
                args[pos] = 1 if isinstance(self._global[arg[:-6]],float) else 0
            elif (
                arg.endswith(".dict??")
                and arg[:-7].isidentifier()
                and arg[:-7] in self._global
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-7]],dict) else 0
            elif (
                arg.endswith(".list??")
                and arg[:-7].isidentifier()
                and arg[:-7] in self._global
            ):
                args[pos] = 1 if isinstance(self._vars[arg[:-7]],tuple) else 0
            ## dictionary interface
            elif arg.startswith("%") and arg.count("->") > 0:
                args[pos] = read(self._vars, arg[1:]) or self.err(
                    "[Error]: Invalid dictionary fetch: " + arg
                )
            elif arg.startswith("local%") and arg.count("->") > 0:
                args[pos] = read(self._vars, arg[6:]) or self.err(
                    "[Error]: Invalid dictionary fetch: " + arg
                )
            elif arg.startswith("global%") and arg.count("->") > 0:
                args[pos] = read(self._global, arg[7:]) or self.err(
                    "[Error]: Invalid dictionary fetch: " + arg
                )
            ## Value fetching
            elif arg.startswith("%") and arg[1:] in self._vars:
                args[pos] = self._vars.get(arg[1:])
            elif arg.startswith("local%") and arg[6:] in self._vars:  # for readability
                args[pos] = self._vars.get(arg[6:])
            elif (
                arg.startswith("global%") and arg[7:] in self._global
            ):  # for readability
                args[pos] = self._global.get(arg[7:])
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
                for name, value in self._vars.items():
                    arg = arg.replace(f".[{name}]", str(value))
                args[pos] = arg
            elif arg.startswith('!"') and arg.endswith('"'):  # vars from global
                arg = arg[2:-1]
                for name, value in self._vars.items():
                    arg = arg.replace(f".[{name}]", str(value))
                args[pos] = arg
            else:
                return str(arg)
        return tuple(args)

    def run(self, code, manual=False, pref="main"):
        comment = "//"
        prog = [
            (
                line.strip()
                if comment not in line
                else line[: line.index(comment)].strip()
            )
            for line in code.split("\n")
        ]
        if len(self.lines) > MAX_SCRIPT_CALLS:
            self.err(
                f"""[Error-Crit]: Too many scripts to handle!
Fixes:
 - Wait until a script finishes to run another script.
 - Look for recursive calls.
 - Put the code in the main script instead of using a separate one.
Causes:
 - Recursive calls (calling the main script in the main script)
 - Running to many scripts, every script, everywhere all at once.
MAX_SCRIPT_CALLS: {MAX_SCRIPT_CALLS}"""
            )
        LINE_INDEX = len(self.lines)
        self.lines.append(0)
        self.p = self.lines[LINE_INDEX]
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
                    self.err("[Error] Pre-runtime: Invalid name: " + args[0])
                self._jtable[args[0]] = line_num
        ## Program execution
        while self.p < len(prog):
            line = prog[self.p]
            if line == tuple():
                self.p += 1
                continue
            ins, pargs = list(line)
            arguments = self._values(list(pargs))
            if type(arguments) == str:
                self._calls.append((self.p, ins, (None,), (*pargs,)))
                self.err(f"[Error]: Encountered invalid argument `{arguments}`.")
            args = tuple(arguments)
            argc = len(args)
            self._calls.append((self.p, ins, (*args,), (*pargs,)))
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
                self._vars[args[0]] = input()
            ## Variables
            elif ins == "set" and argc == 2:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = args[1]
            elif ins == "get_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._global):
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = self._global[args[0]]
            elif ins == "set_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._vars):
                    self.err("[Error]: Invalid name: " + args[0])
                self._global[args[0]] = self._vars[args[0]]
            elif ins == "rename" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._vars):
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._vars[args[1]] = self._vars[args[0]]
            elif ins == "rename_global" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._global):
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._global[args[1]] = self._global[args[0]]
            elif ins == "delete" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._vars):
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars.pop(args[0])
            elif ins == "delete_global" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._global):
                    self.err("[Error]: Invalid name: " + args[0])
                self._global.pop(args[0])
            ## Arithmetic operations
            elif ins == "dec" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    self._vars[args[0]] = self._vars[args[0]] - 1
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "inc" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    self._vars[args[0]] = self._vars[args[0]] + 1
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "add" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] + args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "sub" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] - args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "mul" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] * args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "div" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] / args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "fdiv" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] // args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "pow" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] ** args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "mod":
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = args[0] % args[1]
                except Exception as e:
                    self.err("[Error]: " + str(e))
            ## Comparisons
            elif ins == "ifeq" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = 1 if args[0] == args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "ifne" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = 1 if args[0] != args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "iflt" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = 1 if args[0] < args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            elif ins == "ifgt" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                try:
                    self._vars[args[2]] = 1 if args[0] > args[1] else 0
                except Exception as e:
                    self.err("[Error]: " + str(e))
            ## Control flow
            elif ins == "label" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._jtable[args[0]] = self.p
            elif ins == "goto" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                self.p = self._jtable[args[0]]
            elif ins == "giz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                if args[1] == 0:
                    self.p = self._jtable[args[0]]
            elif ins == "gnz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                if args[1] != 0:
                    self.p = self._jtable[args[0]]
            elif ins == "ggz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    if args[1] > 0:
                        self.p = self._jtable[args[0]]
                except:
                    pass
            elif ins == "glz" and argc == 2:
                if (not args[0].isidentifier()) or (args[0] not in self._jtable):
                    self.err("[Error]: Invalid name: " + args[0])
                try:
                    if args[1] < 0:
                        self.p = self._jtable[args[0]]
                except:
                    pass
            ## Random
            elif ins == "random_choice" and argc == 2:
                if not hasattr(args[0], "__iter__"):
                    self.err("[Error]: Object must be a string, list or a dict!")
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + str(args[1]))
                self._vars[args[1]] = choice_random(args[0])
            elif ins == "random_int" and argc == 3:
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + str(args[1]))
                self._vars[args[2]] = randint(args[0],args[1])
            ## Strings
            elif ins == "length" and argc == 2:
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._vars[args[1]] = len(args[0])
            elif ins == "copy" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._vars[args[1]] = args[0]
            elif ins == "split" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != str:
                    self.err("[Error]: Invalid type: " + str(type(args[0])))
                if type(args[1]) != str:
                    self.err("[Error]: Invalid type: " + str(type(args[1])))
                self._vars[args[0]] = tuple(self._vars[args[0]].split(args[1]))
            elif ins == "join" and argc == 2:
                if (type(self._vars.get(args[1])) != tuple) or args[
                    1
                ] not in self._vars:
                    self.err("[Error]: Invalid data: " + args[1])
                if type(args[0]) != str:
                    self.err("[Error]: Invalid type: " + str(type(args[0])))
                self._vars[args[1]] = args[0].join(self._vars[args[1]])
            elif ins == "string" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                oldp = self.p
                lines_ = []
                scode = code.split("\n")
                while self.p < len(prog):
                    line = prog[self.p][0] if len(prog[self.p]) > 0 else ""
                    if line == f"end:string:{args[0]}":
                        break
                    self.p += 1
                    lines_.append(scode[self.p])
                else:
                    self.p = oldp
                    self.err(f"[Error]: String `{args[0]}` not closed!\nUse `end:string:{args[0]}` to end the string.")
                self._vars[args[0]] = "\n".join(lines_[:-1])
            ## Functions
            elif ins == "pfunc" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._jtable[args[0]] = ("partial:func", None, {})
            elif ins == "func_default_value" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._jtable:
                    self.err(f"[Error]: Invalid name `{args[0]}`.\nplease prototype the function `{args[0]}` before using the `func_default_value` instruction.")
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._jtable[args[0]][2][args[1]] = args[2]
            elif ins == "func" and argc > 0:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                oldp = self.p
                if args[0] not in self._jtable:
                    self._jtable[args[0]] = (self.p, (*args[1:],), {})
                else:
                    vals = list(self._jtable[args[0]])
                    vals[0], vals[1] = (self.p,(*args[1:],))
                    self._jtable[args[0]] = tuple(vals)
                while self.p < len(prog):
                    line = prog[self.p][0] if len(prog[self.p]) > 0 else ""
                    if line == f"end:func:{args[0]}":
                        break
                    self.p += 1
                else:
                    self.p = oldp
                    self.err(f"[Error]: Function `{args[0]}` not closed!\nUse `end:func:{args[0]}` to close the function.")
            elif ins == "return":
                if self._call_stack == []:
                    self.err("[Error]: Invalid return!")
                self.p = self._call_stack.pop()
                for arg in args:
                    if not (arg.isidentifier() and arg in self._vars):
                        self.err("[Error]: Invalid name: " + arg)
                    self._global[arg] = self._vars[arg]
                self.pop_scope()
                self._iter -= 1
            elif ins == "call" and argc > 0:
                if (not args[0].isidentifier()) or args[0] not in self._jtable:
                    self.err("[Error]: Invalid name: " + args[0])
                jump, arg_name, defs = self._jtable[args[0]]
                if jump == "partial:func":
                    self.err(f"[Error]: Function `{args[0]}` not fully defined!")
                self._call_stack.append(self.p)
                self.p = jump
                self.new_scope()
                if self._iter > self._global.get("sys_max_iter", 10_000):
                    self.err(
                        "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz]` for loops!"
                    )
                self._iter += 1
                self._vars.update(defs)
                for name, val in zip(arg_name, args[1:]):
                    if val == ".ignore:arg":
                        continue
                    self._vars[name] = val
                self._vars["_name"] = args[0]
            elif ins in self._jtable and type(self._jtable.get(ins, None)) == tuple:
                jump, arg_name, defs = self._jtable[ins]
                if jump == "partial:func":
                    self.err(f"[Error]: Function `{ins}` not fully defined!")
                self._call_stack.append(self.p)
                self.p = jump
                self.new_scope()
                if self._iter > self._global.get("sys_max_iter", 10_000):
                    self.err(
                        "[Error]: Recursion error!\nAny further can cause the call stack and the scope stack to over flow!\nUse `[goto/giz/gnz/glz/ggz]` for loops!"
                    )
                self._iter += 1
                self._vars.update(defs)
                for name, val in zip(arg_name, args[0:]):
                    if val == ".ignore:arg":
                        continue
                    self._vars[name] = val
                self._vars["_name"] = ins
            elif (
                ins in self._jtable
                and type(self._jtable.get(ins, None)) != tuple
            ):
                self.err(
                    f'[Error]: Label is not callable, use `[goto/giz/gnz/glz/ggz] "{ins}"` instead.'
                )
            ## Packaged function
            elif ins == "ppack" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._func[args[0]] = ("partial:func", None, {})
            elif ins == "pack_default_value" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._func:
                    self.err(f"[Error]: Invalid name `{args[0]}`.\nplease prototype the package `{args[0]}` before using the `pack_default_value` instruction.")
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                self._func[args[0]][2][args[1]] = args[2]
            elif ins == "pack" and argc > 0:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                oldp = self.p
                code_ = []
                scode = code.split("\n")
                while self.p < len(prog):
                    line = prog[self.p][0] if len(prog[self.p]) > 0 else ""
                    if line == f"end:pack:{args[0]}":
                        break
                    code_.append(scode[self.p])
                    self.p += 1
                else:
                    self.p = oldp
                    self.err(f"[Error]: Pack `{args[0]}` not closed!\nUse `end:pack:{args[0]}` to close the function.")
                if args[0] not in self._func:
                    self._func[args[0]] = ("\n".join(code_[1:]), (*args[1:],), {})
                else:
                    vals = list(self._func[args[0]])
                    vals[0], vals[1] = ("\n".join(code[1:]), (*args[1:],))
                    self._func[args[0]] = tuple(vals)
            elif ins == "callp" and argc > 0:
                if (not args[0].isidentifier()) or args[0] not in self._func:
                    self.err("[Error]: Invalid name: " + args[0])
                code, arg_name, defs = self._func[args[0]]
                if code == "partial:func":
                    self.err(f"[Error]: Pack `{args[0]}` not fully defined!")
                self._files.append(f"{self._files[-1]}:{args[0]}")
                self.new_scope()
                self._vars.update(defs)
                for name, val in zip(arg_name, args[1:]):
                    if val == ".ignore:arg":
                        continue
                    self._vars[name] = val
                self._vars["_name"] = args[0]
                self.run(code)
                self.pop_scope()
                self._files.pop()
                self.p = self.lines.pop()+1
                self.lines.append(self.p)
            elif ins.startswith('pack:') and ins[5:] in self._func and type(self._func.get(ins[5:], None)) == tuple:
                ins = ins[5:]
                code, arg_name, defs = self._func[ins]
                if code == "partial:func":
                    self.err(f"[Error]: Pack `{ins}` not fully defined!")
                self._files.append(f"{self._files[-1]}:{ins}")
                self.new_scope()
                self._vars.update(defs)
                for name, val in zip(arg_name, args):
                    if val == ".ignore:arg":
                        continue
                    self._vars[name] = val
                self._vars["_name"] = ins
                self.run(code)
                self.pop_scope()
                self._files.pop()
                self.p = self.lines.pop()+1
                self.lines.append(self.p)
            ## Type casting
            elif ins == "to_int" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._vars):
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = int(self._vars[args[0]])
            elif ins == "to_str" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._vars):
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = str(self._vars[args[0]])
            elif ins == "to_flt" and argc == 1:
                if (not args[0].isidentifier()) or (args[0] not in self._vars):
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = float(self._vars[args[0]])
            ## Errors
            elif ins == "raise_error" and argc == 1:
                self.err(args[0])
            ## Execution
            elif ins == "run_file" and argc == 1:
                if not os.path.isfile(args[0]):
                    self.err("[Error]: File not found: " + args[0])
                self._files.append(f"script:{args[0]}")
                self.run(open(args[0]).read())
                self.p = self.lines.pop()+1
                self.lines.append(self.p)
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
                self._vars[args[1]] = 1 if os.path.isfile(LIBDIR + args[0]) else 0
            elif ins in self._mods:
                self._mods[ins](*args)
            ## System
            elif ins == "sys_console" and argc == 1:
                os.system(args[0])
            elif ins == "sys_atexit":
                lines_ = []
                while self.p < len(prog):
                    line = prog[self.p][0] if len(prog[self.p]) > 0 else ""
                    if line == "close":
                        break
                    lines_.append(code.split("\n")[self.p])
                    self.p += 1
                self.atexit = "\n".join(lines_[1:])
            ## Lists
            elif ins == "list_new" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = tuple()
            elif ins == "list_init" and argc == 1:
                lines_ = []
                scode = code.split("\n")
                oldp = self.p
                while self.p < len(prog):
                    line = prog[self.p][0] if len(prog[self.p]) > 0 else ""
                    if line == f"end:list:{args[0]}":
                        break
                    line = scode[self.p]
                    lines_.append(
                        line.strip()
                        if comment not in line
                        else line[: line.index(comment)].strip()
                    )
                    self.p += 1
                else:
                    self.p = oldp
                    self.err(f"[Error]: List `{args[0]}` not closed!\nUse `end:list:{args[0]}` to close the list.")
                self._vars[args[0]] = self._values(lines_[1:])
            elif ins == "list_make" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = tuple([0] * args[1])
            elif ins == "list_append" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                self._vars[args[0]] = tuple([*self._vars[args[0]], args[1]])
            elif ins == "list_pop" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                self._vars[args[1]] = (
                    [*self._vars[args[0]]].pop() if [*self._vars[args[0]]] else -1
                )
                if [*self._vars[args[0]]]:
                    self._vars[args[0]] = tuple([*self._vars[args[0]]][:-1])
            elif ins == "list_reverse" and argc == 1:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                self._vars[args[0]] = self._vars[args[0]][::-1]
            elif ins == "list_insert" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                if not isinstance(args[1], int):
                    self.err("[Error]: Invalid type for an index!")
                self._vars[args[0]][args[1]] = args[2]
            elif ins == "list_get" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != tuple:
                    self.err("[Error]: Invalid data type! Variable is not for a list!")
                if not isinstance(args[1], int):
                    self.err("[Error]: Invalid type for an index!")
                if not args[2].isidentifier():
                    self.err("[Error]: Invalid name: " + args[2])
                self._vars[args[2]] = self._vars[args[0]][args[1]]
            ## Dictionaries
            elif ins == "dictionary_new" and argc == 1:
                if not args[0].isidentifier():
                    self.err("[Error]: Invalid name: " + args[0])
                self._vars[args[0]] = {}
            elif ins == "dictionary_add_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != dict:
                    self.err(
                        "[Error]: Invalid data type! Variable is not a dictionary: "
                        + str(args[2])
                    )
                if id(self._vars[args[0]]) == id(args[2]) and type(args[2]) == dict:
                    self._vars[args[0]][args[1]] = args[2].copy()
                else:
                    self._vars[args[0]][args[1]] = args[2]
            elif ins == "strict_dictionary_add_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != dict:
                    self.err(
                        "[Error]: Invalid data type! Variable is not a dictionary!: "
                        + str(args[2])
                    )
                self._vars[args[0]][args[1]] = args[2]
            elif ins == "dictionary_get_item" and argc == 3:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != dict:
                    self.err("[Error]: Invalid data type")
                self._vars[args[2]] = self._vars[args[0]].get(args[1], 0)
            elif ins == "dictionary_pop_item" and argc == 2:
                if (not args[0].isidentifier()) or args[0] not in self._vars:
                    self.err("[Error]: Invalid name: " + args[0])
                if type(self._vars[args[0]]) != dict:
                    self.err("[Error]: Invalid data type!")
                self._vars[args[0]].pop(args[1], 0)
            ## File IO
            elif ins == "read_file" and argc == 2:
                if not args[1].isidentifier():
                    self.err("[Error]: Invalid name: " + args[1])
                if not os.path.isfile(args[0]):
                    self.err("[Error]: Invalid file: " + args[0])
                self._vars[args[1]] = open(args[0]).read()
            elif ins == "write_file" and argc == 2:
                open(args[0], "w").write(str(args[1]))
            elif ins == "append_file" and argc == 2:
                open(args[0], "a").write(str(args[1]))
            ## File operations
            elif ins == "isfile" and argc == 2:
                if not args[1].isidentifier():
                    self.err(f"[Error]: Invalid name: {args[1]}")
                self._vars[args[1]] = 1 if os.path.isfile(args[0]) else 0
            elif ins == "isdir" and argc == 2:
                if not args[1].isidentifier():
                    self.err(f"[Error]: Invalid name: {args[1]}")
                self._vars[args[1]] = 1 if os.path.isdir(args[0]) else 0
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
            self.p += 1
            self.lines[LINE_INDEX] = self.p
        self.p = self.lines.pop() if len(self.lines) > 1 else float("inf")

    def err(self, msg="", csgui=True):
        if self._calls:
            print("======== [ Error ] ========")
            print("\nMost recent call last:")
            for pos, [line, ins, args, pargs] in enumerate(self._calls):
                if len(self._calls) > 100 and len(compress(self._calls)) < 100:
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
                                    "   Function parameters:", self._jtable.get(ins)[1]
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
                if len(self._calls) > 100 and len(compress(self._calls)) > 100:
                    print(
                        f"Estimated {len(self._calls)*3:,}~ Lines of error output...\nDid not print call back. This is just a sub set."
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
        print(
            "======== [ Details ] ========\n"
            + msg
            + f"\nError found at line {(self.p+1 if type(self.p) == int else '[OutOfBounds]')}\nIn file `{self._files[-1] if self._files else '[OutOfBounds]'}`\n"
        )
        self.p = float("inf")
        self._csgui()

    def csgui(self):
        self.p = float("inf")
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
                        f"Line: {line}\nInstruction: {ins}\nArguments: {pargs}\nProcessed arguments: {args}\nMod: {ins in self._mods}\nFunction: {ins in self._jtable and type(self._jtable.get(ins)) == tuple}"
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
        self.p = float("inf")

    def exit(self):
        if self.atexit != None:
            self.run(self.atexit)
        self.p = float("inf")

    def set_exit_method(self, function):
        self._exit_method = function

    def remove_csgui(self):
        self._csgui = lambda: None
