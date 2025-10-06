# Open a file for reading
f = open('test.txt')  # Opens an existing file in the same directory
print(f.read())       # Reads the whole file content
f.close()             # Always close after operations

# Create and open a file for writing
f = open("foo.txt", "w+")
f.write("This is a sample text.\nSecond line here.\n")
f.seek(0)             # Go back to start to read
print(f.read())
f.close()

f = open('test.txt', 'r')
print(f.read(10))        # Reads just 10 characters
f.seek(0)                # Cursor to beginning
print(f.readline())      # Reads one line
f.seek(0)
print(f.readlines())     # Reads all lines as list
f.close()

# Using 'with' for safe file operations (no need to close)
with open('myfile.txt', 'r') as my_new_file:
    contents = my_new_file.read()
    print(contents)

# File modes demonstration
# Read mode
with open('test.txt', mode='r') as f:
    print(f.read())

# Append mode
with open('test.txt', mode='a') as f:
    f.write('\nfourth line')

# Write mode (creates new file if not exists)
with open('xcvdf.txt', mode='w') as f:
    f.write('created new file')


import os

# Remove a file
with open('demofile.txt', mode='w') as f:
    f.write('created new file')
os.remove("demofile.txt")   # Deletes the file

# Check if a file exists
print(os.path.exists("tesht.txt"))

# Append mode to a file in directory
file2 = open('text.txt', 'a+')
file2.write('3rd line\nfourth line')
file2.close()
