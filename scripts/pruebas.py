import json
import os


# Environment variables
CWD = os.path.dirname(__file__)
READ_INFO = os.path.join(CWD,"templates", "readInfo.json")

with open(READ_INFO, "r") as f:
    return_info = json.load(f)

print(f"{type(return_info)}: {return_info}")
print(return_info["extractTime"])

mylist = [1.3,2.5,3.0,4.1,5.3]

for i in range(len(mylist)):
    return_info["extractReliability"]["Page "+str(i+1)] = str(mylist[i])

reliability_list = []

for e in mylist: 
    reliability_list.append(str(e))
print("RELIABILITY_LIST")
print(reliability_list)

print(return_info)

return_info["extractPageMark"] = mylist
print(return_info["extractPageMark"])
print(return_info)
