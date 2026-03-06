
def Fibonacci(n):

    a = [0, 1]
    if n < 2:
        print(a[:n+1])
    else:
        for i in range(2, n):
            a.append(a[i-1] + a[i-2])
    
    print(a[:n+1])


Fibonacci(50)