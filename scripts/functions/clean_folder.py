import os

def clean_folder(path):
    print('cleaning folder')
    print('folder: ', path)
    files = os.listdir(path)
    print('files: ', files)
    for file_name in os.listdir(path):
        
        new_file = path + '/' + file_name
        print(new_file)
        print('size: ', os.path.getsize(new_file))
        print('is file? ', os.path.isfile(new_file))
        if os.path.isfile(new_file):
            print('Deleting file: ', new_file)
            os.remove(new_file)
    print('end cleaning folder')