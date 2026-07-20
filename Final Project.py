"""
Author: Olusola Awosanya
Date: 05/04/2025
Purpose: Calculating teacher bonus based on years of service

#input
     enter teacher's name - name
     enter current salary - salary
     enter years of emplyment - years

#processing
     determine bonus percent based on years
     calculate bonus amount and new salary

#output
     display name, current salary, years of employment, bonus amount, and new salary
"""

# Input
name = input("Enter teacher's name: ")
salary = float(input("Enter current salary: $"))
years = int(input("Enter years of employment: "))

# Processing
if years < 1:
    bonus_percent = 0
elif years <= 5:
    bonus_percent = 5
elif years <= 10:
    bonus_percent = 10
elif years <= 15:
    bonus_percent = 15
else:
    bonus_percent = 20

bonus = salary * bonus_percent / 100
new_salary = salary + bonus

# Output
print()
print("Name:", name)
print("Current Salary: $", f"{int(salary):,}")
print("Years of Service:", years)
print("Amount of Bonus: $", f"{int(bonus):,}")
print("New Salary: $", f"{int(new_salary):,}")
