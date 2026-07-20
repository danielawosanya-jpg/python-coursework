"""
Author: Olusola Awosanya
Date:04/07/2025
Purpose:creating program that displays an employee’s name,
hourly wage, ,total hours worked,overtime hours, total gross weekly pay.

#Input
Employee name. employee_name
Hourly wage.  Hourly_wage float
Hours worked. Hours_worked float

#processing
if(hours_worked > 40):
    overtime_hours = hours_worked - 40
    overtime_pay = overtime_hours * hourly_wage * 1.5
    regular_pay = 40 * hourly_wage
    gross_pay = overtime_pay + regular_pay
else:
    gross_pay = hours_worked * hourly_wage

#Output
Print employee_name
print hourly_wage
print hours worked
print overtime_hours
print overtime pay
print regular pay
print gross pay

"""

#input
employee_name = input("Enter the employee's name: ")
hourly_wage = float(input("Enter the hourly wage: $"))
hours_worked = float(input("Enter the total number of hours worked: "))

#processing
if(hours_worked > 40):
    overtime_hours = hours_worked - 40
    overtime_pay = overtime_hours * hourly_wage * 1.5
    regular_pay = 40 * hourly_wage
    gross_pay = overtime_pay + regular_pay
    print("")
    print("")
    print("Employee Name:", employee_name)
    print("Hourly Wage: $", hourly_wage)
    print("Total Regular Pay:", regular_pay)
    print("Total Overtime Hours:", overtime_hours)
    print("Total Overtime Pay:", overtime_pay)
    print("Total Gross Weekly Pay: $", gross_pay)
else:
    gross_pay = hours_worked * hourly_wage
    print("")
    print("")
    print("Employee Name:", employee_name)
    print("Hourly Wage: $", hourly_wage)
    print("Total Hours Worked:", hours_worked)
    print("Total Gross Weekly Pay: $", gross_pay)