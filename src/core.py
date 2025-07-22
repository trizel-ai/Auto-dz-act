# core.py – AUTO DZ ACT: Symbolic Validation Core (STOE V12–V22)

def validate_theoretical_prediction(theoretical, experimental, epsilon=0.01, delta=0.1):
    """
    Compares a theoretical value with an experimental result.
    Returns a symbolic code: '0/0', 'D0/DZ', or 'DZ'.

    Parameters:
    - theoretical: expected value from STOE model
    - experimental: measured value
    - epsilon: small tolerance range for perfect match
    - delta: upper bound for tolerable deviation

    Returns:
    - validation_code: one of '0/0', 'D0/DZ', or 'DZ'
    """

    deviation = abs(theoretical - experimental)

    if deviation < epsilon:
        return '0/0'       # Perfect match
    elif epsilon <= deviation < delta:
        return 'D0/DZ'     # Partial deviation
    else:
        return 'DZ'        # Major deviation

# Example usage
if __name__ == "__main__":
    T = 5.82        # Theoretical ∇S from STOE
    E = 5.80        # Measured experimental ∇S
    code = validate_theoretical_prediction(T, E)
    print("Validation Code:", code)
