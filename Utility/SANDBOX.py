class Human():

    def __init__(self, age):
        self.age = age

    def __str__(self):
        return f'Hello, my age is {self.age}'


paz = Human(20)

roni = Human(30)

print(dir(paz))

print(paz)
print(roni)