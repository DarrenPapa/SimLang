# Python Extension Files For SimLang

# A decorator is used to register a function `@inter.add_mod` it takes in two
# arguments, the name and the number of args. When included its name will
# be [module_name]-[instruction_name], if you need a infinite number of args
# use -1

# Example
@inter.add_mod("test",0)
def _(self):
    print("Ok :)")

# You can add data that can be accessed by other extensions by using
# `inter.data.add_sector` it takes one argument the sector name
# the sector name must be a valid identifier since after making the
# sector you can access it using inter.data.name_here

# Example
inter.data.add_sector('test')

# You can assign values to this object.
# it is the same object as inter.data so you can nest and organize data.

# Example
inter.data.test.name = "test"
inter.data.test.add_sector("test1")
inter.data.test.test1.name = "test1"

# The first sector (the root) must be the name of the module

# You can get other sectors by doing
mod = inter.data["test"]
# It will return `None` if it doesnt exist

# You can also remove sectors but it is not encouraged
inter.data.rem_sector("test")

# The `inter` object is the current interpreter instance, it is in the global scope
# of an extension script when it is included, if it is ran separately from the
# interpreter, it will raise `NameError` since inter doesnt exist when an extension
# is normally ran.

# SimLangs variables that are used during runtime

inter._vars   # The local scope
inter._global # The global scope
inter._jtable # Labels and functions, functions are stored as tuples ->
              # (line:int, parameters:tuple, default_values:dict)
              # while labeles are just integers of what line they are
              # the lines are thier index in the code
inter._calls  # The call stack that the error traceback looks at
inter._lines  # The list of lines of the current scripts running
inter.p       # The current line of the current script