"""
Author:Olusola Awosanya
Date: 04/08/2025
Purpose: creating a program that calculates discounts.

input

cost of meal - meal_cost float

Processing 

if (meal_cost > 25):
    tax = .06 * meal_cost
    tip = .07 * meal_cost
    total_cost = meal_cost + tax + tip
    discount = .10 * meal_cost
    balance = total_cost - discount
else:
    tax = .06 * meal_cost
    tip = .07 * meal_cost
    total_cost = meal_cost + tax + tip
    
output

print("")

"""

#input

meal_cost = float(input("Enter meal cost: "))

#Processing
if (meal_cost > 25):
    tax = .06 * meal_cost
    tip = .07 * meal_cost
    total_cost = meal_cost + tax + tip
    discount = .10 * meal_cost
    balance = total_cost - discount
    print("*****************************")
    print("")
    print("The cost of your meal is: $", meal_cost)
    print("The tax on your meal is: $", tax)
    print("The tip on your meal is: $", tip)
    print("The totall cost for your meal is: $", total_cost)
    print("*****************************")
    print("The discount on your meal is: $", discount)
    print("The total balance of your meal is: $", balance)
    print("")
else:
    tax = .06 * meal_cost
    tip = .07 * meal_cost
    total_cost = meal_cost + tax + tip
    print("*****************************")
    print("")
    print("The cost of your meal is: $", meal_cost)
    print("The tax on your meal is: $", tax)
    print("The tip on your meal is: $", tip)
    print("*****************************")
    print("The total cost for your meal is: $", total_cost)
    print("")
