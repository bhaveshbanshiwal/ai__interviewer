import time

OLD = ""

n = 1
while True:
    if OLD.count("\n")+1 < open('code.bin', 'r').read().count("\n"):
        print(OLD.count("\n"), open('code.bin', 'r').read().count("\n"))
        OLD = open('code.bin', 'r').read()
        # Here to add command for actions
        print("Code changed")
    time.sleep(1)
    print(f"Bot, cycle no - {n}")


    n += 1