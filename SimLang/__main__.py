#!/usr/bin/python
import os
import sys
import traceback
from sys import exit  # for pyinstaller
from time import perf_counter as time
import interpreter

## Handle local dir and where to put libs folder
os.chdir(os.getcwd())
LOCALDIR = os.getcwd() + "/"
del sys.path[0]
sys.path[0] = LOCALDIR
if os.name == "nt":
    HOST_OS = sys.platform
    LIBDIR = os.path.join(os.getenv("APPDATA"),"simlang_libs")+"\\"
    MODDIR = os.path.join(os.getenv("APPDATA"),"simlang_modules")+"\\"
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
## Handle libs folder
if not os.path.isdir(LIBDIR):
    os.mkdir(LIBDIR[:-1])
## Handle mods folder
if not os.path.isdir(MODDIR):
    os.mkdir(MODDIR[:-1])

if len(sys.argv) < 2:
    INTERPRETER = interpreter.inter_class('./','script:REPL')
    INTERPRETER.rm_exit_method()
    print(
        '[ SL REPL 0.1 ] Might be slower due to the REPL\'s argument handling. "exit" to exit.'
    )
    print(
        f'System: {HOST_OS}\nLibs directory: "{LIBDIR}"\nModules directory: "{MODDIR}"\nLocal directory: "{LOCALDIR}"'
    )
    while True:
        act = input("Code >> ")
        if act == "exit":
            exit("[Done]")
        elif act.startswith(":term:"):
            os.system(act[6:])
        elif act.startswith(":exec:"):
            try:
                exec(act[6:])
            except BaseException:
                print(traceback.format_exc())
        elif act == ":const:localdir":
            print(LOCALDIR)
        elif act == ":const:moddir":
            print(MODDIR)
        elif act == ":const:libdir":
            print(LIBDIR)
        elif act == ":const:system":
            print(HOST_OS)
        elif act == ":multiline":
            code = ""
            print("Multi-line mode, Enter `exit` on a newline to exit.\n`run` to run code.\n`reset` to clear code.\n`run` to run code. `list` to see code.")
            iter = 0
            while True:
                k = input(f"[{str(iter).zfill(3)}] + ")
                if k == "exit":
                    break
                elif k == "reset":
                    iter = 0
                    code = ""
                elif k == "run":
                    INTERPRETER.run(code)
                elif k == "list":
                    print(code.strip())
                else:
                    if k:
                        code += k+"\n"
                        iter += 1
        else:
            try:
                INTERPRETER.run(act)
            except KeyboardInterrupt:
                print("[Exited]")
                sys.exit()
            except SystemExit:
                sys.exit()
            except BaseException:
                print(" [ INTERPRETER ERROR ] ".center(88, "="))
                INTERPRETER.err(traceback.format_exc())
                print(f"Last Instruction: {INTERPRETER._calls[-1]}")
        INTERPRETER._calls = []
if not os.path.isfile(sys.argv[1]):
    exit("[Error]: Argument one must be file!")
ok = interpreter.inter_class(sys.argv[1],sys.argv[1])
try:
    start = time()

    def __exit(msg=""):
        if "--time" in sys.argv or "-t" in sys.argv:
            print(f"Time elapsed: {time()-start:.6f}s")
        sys.exit(msg)

    if "--time" in sys.argv or "-t" in sys.argv:
        ok.exit = __exit
    with open(sys.argv[1], "r") as file:
        ok.run(file.read())
except SystemExit:
    sys.exit()
except KeyboardInterrupt:
    print("[Exited]")
    sys.exit()
except:
    print(" [ INTERPRETER ERROR ] ".center(88, "="))
    ok.err(traceback.format_exc())
    print(f"Last Instruction: {ok._calls[-1]}")
