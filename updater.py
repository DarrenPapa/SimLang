import requests

def update(file,content,vfile,version):
    open(file,"w").write(content)
    open(vfile,"w").write(str(version))

def check_for_update(cv_i,cv_m):
    uc_inter = "https://chasedevelopmentgroup.pythonanywhere.com/check_version_inter"
    uc_main = "https://chasedevelopmentgroup.pythonanywhere.com/check_version_main"
    try:
        print("Updater: Getting interpreter version...")
        print(f"Caching interpreter code...")
        gf_i = requests.get("https://chasedevelopmentgroup.pythonanywhere.com/get_inter").text
        ruc_inter = requests.get(uc_inter)
        print("Updater: Getting interface version...")
        print(f"Caching interface code...")
        gf_m = requests.get("https://chasedevelopmentgroup.pythonanywhere.com/get_main").text
        ruc_main = requests.get(uc_main)
        ruc_iv = float(ruc_inter.text)
        ruc_mv = float(ruc_main.text)
        FORCE_i = False
        FORCE_m = False
        ups = 0
        
        if ruc_iv > cv_i: ups += 1; print("New interpreter update...")
        if ruc_mv > cv_m: ups += 1; print("New interface update...")
        
        print(f"Updater: Updates {ups} detected.")
        if ups == 0 and gf_i != open("SimLang/interpreter.py","r").read():
            print("""Updater [Error]: CORRUPTED INTERPRTER!
CAUSES:
 - THE INTERPRETER WAS MODIFIED.
 - FILE WAS CORRUPTED.
 - SERVER FILE WAS CORRUPTED.""")
            if input("[y/n] Continue update anyway?: ").lower() == "y":
                FORCE_i = True
        if ups == 0 and gf_m != open("SimLang/__main__.py","r").read():
            print("""Updater [Error]: CORRUPTED INTERFACE!
CAUSES:
 - THE INTERFACE WAS MODIFIED.
 - FILE WAS CORRUPTED.
 - SERVER FILE WAS CORRUPTED.""")
            if input("[y/n] Continue update anyway?: ").lower() == "y":
                FORCE_m = True
        if ups == 0 and not (FORCE_i or FORCE_m):
            print("Updater: All files up to date!")
            return
        if FORCE_i:
            print("Updater [Force]: Updating intertpreter...")
            update("SimLang/interpreter.py",gf_i,"SimLang/v_i.txt",ruc_iv)
            print("Uodater [Force]: Updated interpreter.")
        if FORCE_m:
            print("Updater [Force]: Updating interface...")
            update("SimLang/__main__.py",gf_m,"SimLang/v_m.txt",ruc_mv)
            print("Updater [Force]: Updated interface.")
            
        if FORCE_m or FORCE_i:
            return
        if ruc_iv > cv_i and not FORCE_i:
            if input(
                f"Updater: New version for the interface available.\nNew Version: {ruc_iv}\nOld Version: {cv_i}\nUpdate interpreter? [Y/N]: "
            ).lower() == "y":
                update("SimLang/interpreter.py",gf_i,"SimLang/v_i.txt",ruc_iv)
                print("Updated interpreter!")
            else:
                print("Updater: Aborted...")
        else:
            print(f"Updater: Interpreter is up to date!")
        if ruc_mv > cv_m and not FORCE_m:
            if input(
                f"Updater: New version for the interface available.\nNew Version: {ruc_mv}\nOld Version: {cv_m}\nUpdate interface? [Y/N]: "
            ).lower() == "y":
                update("SimLang/__main__.py",gf_m,"SimLang/v_m.txt",ruc_mv)
                print("Updated interface!")
            else:
                print("Updater: Aborted...")
        else:
            print("Updater: Interface is up to date!")
            
    except requests.RequestException as e:
        print(f"Error checking for update: {e}")
    except ValueError as e:
        print(f"Error: The server might be down!\n{e}")

if __name__ == "__main__":
    cv_i, cv_m = float(open("SimLang/v_i.txt").read()), float(open("SimLang/v_m.txt").read())
    check_for_update(cv_i, cv_m)