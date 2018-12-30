# shell-like
a simple python toy. you can create a shell-like application with it.

## usage
```python
import time
with Shell(prompt = lambda: "\033[38;5;2mlambor\033[0m " + time.strftime("%Y-%m-%d %H:%M:%S") +"> ", 
    auto_complete = lambda predix: ['a','hello','where','1234567','jjjjjjjjjjjjjjjj','1','2','3']) as shell:
    shell.run(onCommand = lambda cmdline: print("your input: " + cmdline))
```

## features
> + it only support unix-like platform
> + it supports serveral normal shortcuts, like `ctrl+d` `ctrl+a` `ctrl+e` `ctrl+u` `ctrl+w`. they work similarly as on a linux console.
> + it has a history function. you can toggle it by `arrow-up` or `arrow-down`
> + it has an auto-complete function. you can toggle it by `tab`