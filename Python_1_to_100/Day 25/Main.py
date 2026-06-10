# with open("./Day 25/weather_data.csv") as data_file:
#     data = data_file.readlines()
#     print(data)


# import csv
# with open("./Day 25/weather_data.csv") as data_file:
#     data = csv.reader(data_file)
#     temp = []
#     for row in data:
#         if row[1] != "temp":
#             temp.append(int(row[1]))
#     print(temp)


import pandas

data = pandas.read_csv("./Day 25/weather_data.csv")
# print(data['temp'])


monday = data[data.day == "Monday"]
print(monday)
monday_temp = monday.temp[0]
print(monday_temp)
monday_temp_f = monday_temp * 9/5 +32
print(monday_temp_f)