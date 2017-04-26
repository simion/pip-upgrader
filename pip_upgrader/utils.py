def user_input(prompt=None):
    try:
        input_func = raw_input
    except NameError:
        input_func = input
    return input_func(prompt)