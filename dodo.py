import os


def task_pylint():
    return {
        'actions': ['pylint src'],
        'clean': True
    }

def task_flake():
    return {
        'actions': ['flake8 src'],
        'clean': True
    }

def task_execute():
    return {
        'actions': ['python3 src/blogscrapper.py'],
        'clean': True
    }
