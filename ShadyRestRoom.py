"""


Author: Olusola Awosanya  
Date: 04/16/2025  
Purpose: Determining room prices at Shady Rest Hotel  

#input  
     Enter room choice - choice - int 
0
#processing  
     Determine room type and price  

#output  
     Display room type and price  
"""

#Input
choice = int(input("Enter your room choice (1 = Queen, 2 = King, 3 = King + Couch): "))

#Processing
if choice in [1]:
    room_type = "Queen"
    price = 125
elif choice in [2]:
    room_type = "King"
    price = 139
elif choice in [3]:
    room_type = "King + Pullout Couch"
    price = 165
else:
    room_type = "Invalid"
    price = 0

#Output
print("")
print("Choice:", choice)

if choice in (1, 2, 3):
    print("Room Type:", room_type)
    print("Price: $", price)
else:
    print("ERROR – You entered an invalid selection, please enter 1, 2, or 3.")

