"""
A test module demonstrating basic function definition, testing, and execution.

This module contains a simple function that doubles a number, along with
a test function and a main execution block to demonstrate its usage.
"""

def test_function(number: int) -> int:
    """
    Multiply a number by 2.
    
    Args:
        number: An integer to be multiplied by 2
        
    Returns:
        The input number multiplied by 2
        
    Example:
        >>> test_function(5)
        10
    """
    return number * 2


def test_test_function() -> None:
    """
    Test function to verify that test_function works correctly.
    
    This function tests the test_function with various inputs to ensure
    it returns the expected results.
    """
    # Test case 1: Positive number
    result1 = test_function(5)
    assert result1 == 10, f"Expected 10, got {result1}"
    
    # Test case 2: Zero
    result2 = test_function(0)
    assert result2 == 0, f"Expected 0, got {result2}"
    
    # Test case 3: Negative number
    result3 = test_function(-3)
    assert result3 == -6, f"Expected -6, got {result3}"
    
    # Test case 4: Large number
    result4 = test_function(1000)
    assert result4 == 2000, f"Expected 2000, got {result4}"
    
    print("All tests passed successfully!")


if __name__ == "__main__":
    """
    Main execution block that demonstrates the function usage.
    
    This block:
    1. Runs the test function to verify correctness
    2. Demonstrates the function with sample inputs
    3. Shows how to use the function in a real scenario
    """
    print("Running test_module.py...")
    print("=" * 40)
    
    # Run tests
    print("Running tests...")
    test_test_function()
    print("=" * 40)
    
    # Demonstrate function usage
    print("Demonstrating function usage:")
    sample_inputs = [1, 5, 10, -2, 0]
    
    for num in sample_inputs:
        result = test_function(num)
        print(f"test_function({num}) = {result}")
    
    print("=" * 40)
    print("Module execution completed successfully!")