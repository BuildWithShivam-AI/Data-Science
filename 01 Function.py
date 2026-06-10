#why function ??
'''
1. To make code resuble 
2. To make code extansive
3. To Make code Readable

'''


def welcome():
    return "Shivam Function is ready"

print(welcome())
print(welcome())

#function to add even or odd number 

def even_odd_sum(lst):
    even_sum = 0
    odd_sum = 0
    for i in lst:
        if i%2 == 0:
            even_sum += i
        else:
            odd_sum += i
    return even_sum,odd_sum

sum1 , sum2 = even_odd_sum([1,3,4,5,3,2,4,5,6,23,34,55,54])
print(sum1,sum2)


def hello(*args, **kwargs):
    '''
    args take the call function contain only value 
    kwargs take data there params + value present in call function
    '''

    print(args)
    print(kwargs)


hello("shivam with args",last ="jadoo is happing ")
