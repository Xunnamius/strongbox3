#!/usr/bin/env python3

import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

ALPHABET = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o',
    'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D',
    'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S',
    'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '1', '2', '3', '4', '5', '6', '7', '8',
    '9', '0', ' ', '-', '_', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')',
    '=', '+', '[', ']', '{', '}', ';', ':', '"', "'", ',', '<', '.', '>', '/',
    '?', '\\', '|', '~', '`'
]

AES_KEY = bytearray(os.urandom(32))
XTS_TWEAK = bytearray(os.urandom(16))

realPassword = input('Enter the real password: ')
guessPassword = ''

# * Oracle1
def guessMatchesRealPassword():
    return realPassword == guessPassword

# * Oracle2
def getEncryptedDifference(localPasswordGuess):
    matches = 0
    for ndx in range(len(localPasswordGuess)):
        matches += 1 if localPasswordGuess[ndx] == realPassword[ndx] else 0

    backend = default_backend()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.XTS(XTS_TWEAK), backend=backend)
    encryptor = cipher.encryptor()

    return encryptor.update(bytearray(str(matches).zfill(16), 'utf8')) + encryptor.finalize()

realPasswordLength = len(realPassword)
alphabetLength = len(ALPHABET)
wrongCharacterCiphertext = None

assert len(ALPHABET) >= 3

n = 1

while n <= realPasswordLength:
    i = 0

    ciphertext1 = getEncryptedDifference(guessPassword + ALPHABET[i])
    i += 1
    ciphertext2 = getEncryptedDifference(guessPassword + ALPHABET[i])

    if ciphertext1 == ciphertext2:
        wrongCharacterCiphertext = ciphertext1

        while i < alphabetLength:
            i += 1
            assert wrongCharacterCiphertext is not None
            if wrongCharacterCiphertext != getEncryptedDifference(guessPassword + ALPHABET[i]):
                n += 1
                guessPassword += ALPHABET[i]
                break

    else:
        i += 1
        n += 1
        ciphertext3 = getEncryptedDifference(guessPassword + ALPHABET[i])

        if ciphertext1 == ciphertext3:
            guessPassword += ALPHABET[i-1]

        elif ciphertext2 == ciphertext3:
            guessPassword += ALPHABET[i-2]

        else:
            print('FAILED: Encountered an impossible scenario')
            exit(2)

    if guessMatchesRealPassword():
        print('Guessed password "{}" successfully'.format(guessPassword))
        exit(0)

print('FAILED: i ({}) >= alphabetLength ({}) or n ({}) > realPasswordLength ({})'.format(i, alphabetLength, n, realPasswordLength))
exit(1)
