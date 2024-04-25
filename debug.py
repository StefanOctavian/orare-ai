def diff():
    log45 = open("debug45.log", 'r')
    log46 = open("debug46.log", 'r')
    lines45 = iter(log45.readline, '')
    lines46 = iter(log46.readline, '')
    lineno = 1
    while True:
        try:
            line45 = next(lines45)
            line46 = next(lines46)
            if line45 == line46:
                print(str(lineno) + '| ' + line45)
            else:
                print(str(lineno) + '< | ' + line45)
                print(str(lineno) + '> | ' + line46)
                break
            lineno += 1
        except StopIteration:
            break
    log45.close()
    log46.close()

diff()

