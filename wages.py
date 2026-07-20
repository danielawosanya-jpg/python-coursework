"""

Author: Olusola Awosanya
Date:03/26/2025
Purpose:a program that takes as inputs the employee's name, the hourly wage,
total regular hours, and total overtime hours and displays an employee’s name,
hourly wage, total regular hours, total overtime hours, total weekly pay.

#Input
Employee name. employee_name
Hourly wage.  Hourly_wage int
Regular hours. Regular_hours int
overtime hours. overtime_hours int

#processing

regular_pay = hourly wage * regular_hours
overtime_pay = 1.5 * hourly_wage * overtime_hours
total_weekly_pay =regular_pay + overtime_pay

#Output
Print employee_name
print hourly_wage
print regular_hrs
print overtime_hours

"""

#input
employee_name = input("Enter the employee's name: ")
hourly_wage = int(input("Enter the hourly wage: "))
regular_hours = int(input("Enter the total number of regular hours worked: "))
overtime_hours = int(input("Enter the total number of overtime hours worked: "))

#processing
regular_pay = hourly_wage * regular_hours
overtime_pay = 1.5 * hourly_wage * overtime_hours
total_weekly_pay = regular_pay + overtime_pay

#output
print("Employee Name:", employee_name)
print("Hourly Wage: $", hourly_wage)
print("Total Regular Hours:", regular_hours)
print("Total Overtime Hours:", overtime_hours)
print("Total Weekly Pay: ", total_weekly_pay)
