"""Name-only experimental feature. No party, outcomes, or biography inputs."""
import math
import re
import unicodedata


def components(name):
    text = ''.join(c for c in unicodedata.normalize('NFKD', name.lower()) if not unicodedata.combining(c))
    words = re.findall(r'[a-z]+', text)
    letters = ''.join(words)
    if not letters:
        return dict(length=0., rhythm=0., alliteration=0., ease=0., distinctiveness=0.)
    syllables = [max(1, len(re.findall(r'[aeiouy]+', w))) for w in words]
    # Fixed, inspectable heuristics, specified before fitting their influence.
    length = math.exp(-((len(letters) - 12) / 9) ** 2)
    rhythm = 1 / (1 + abs(sum(syllables) - 4))
    alliteration = float(len(words) > 1 and words[0][0] == words[-1][0])
    hard_clusters = len(re.findall(r'[^aeiouy]{4,}', letters))
    ease = 1 / (1 + hard_clusters)
    distinctiveness = len(set(letters)) / len(letters)
    return dict(length=length, rhythm=rhythm, alliteration=alliteration, ease=ease, distinctiveness=distinctiveness)


def score(name):
    """Return 0..1, or None for missing names; missing is never a made-up name."""
    if not name or not re.search('[a-zA-Z]', unicodedata.normalize('NFKD', name)):
        return None
    return sum(components(name).values()) / 5


def difference(name_a, name_b):
    a, b = score(name_a), score(name_b)
    return (a - b, False) if a is not None and b is not None else (0., True)
