"""
Inflectional morphology with WFSTs
Code for Arizona submission to sigmorphon2023part1
Alice Kwak, Mike Hammond, Cheyenne Wing
"""

from pyfoma import FST
import os
import multiprocessing
import numpy
import re

# change the path below to your folder containing data
#loc = '/path/to/your/data/'
loc = 'data'
outpath = os.path.join('out', 'sys3')

def ed(s,t):
	'''edit distance'''
	m,n = len(s),len(t)
	d = numpy.zeros(shape=(m + 1,n + 1))
	for i in range(1,m + 1): d[i,0] = i
	for j in range(1,n + 1): d[0,j] = j
	for j in range(1,n + 1):
		for i in range(1,m + 1):
			if s[i - 1] == t[j - 1]:
				subcost = 0
			else:
				subcost = 1
			d[i,j] = min(
				d[i-1,j]+1,d[i,j-1]+1,d[i-1,j-1]+subcost
			)
	return d[m,n],d

def changes(s,t):
	'''extract edits from edit distance output'''
	_,d = ed(s,t)
	m,n = len(s),len(t)
	res = []
	while m > 0 or n > 0:
		delscore = d[m - 1,n] if m >= 1 else float('inf')
		insertscore = d[m,n - 1] if n >= 1 else float('inf')
		subnoopscore = d[m - 1,n - 1] if m >= 1 \
			and n >= 1 else float('inf')
		smallest = min(delscore,insertscore,subnoopscore)
		if smallest == subnoopscore:
			res.append(f'{s[m - 1]}:{t[n - 1]}')
			m -= 1
			n -= 1
		elif smallest == delscore:
			res.append(f"{s[m - 1]}:''")
			m -= 1
		elif smallest == insertscore:
			res.append(f"'':{t[n - 1]}")
			n -= 1
	return res[::-1]

def makerule(b,ml):
	'''make re from edits'''
	reg = []
	s = len(b)
	bitspan = ''
	for change in b:
		bit1,bit2 = change.split(':')
		bit1 = re.sub("-","\-",bit1)
		bit2 = re.sub("-","\-",bit2)
		bit1 = re.sub("_","\_",bit1)
		bit2 = re.sub("_","\_",bit2)
		bit1 = re.sub("\(","\\(",bit1)
		bit2 = re.sub("\(","\\(",bit2)
		bit1 = re.sub("\)","\\)",bit1)
		bit2 = re.sub("\)","\\)",bit2)
		bit1 = re.sub(",","\\,",bit1)
		bit2 = re.sub(",","\\,",bit2)
		bit1 = re.sub("\*","\\*",bit1)
		bit2 = re.sub("\*","\\*",bit2)
		if bit1 == "'": bit1 = "\\'"
		if bit2 == "'": bit2 = "\\'"
		if bit1 == " ": bit1 = "' '"
		if bit2 == " ": bit2 = "' '"
		bit = ''
		if bit1 != bit2:
			if len(bitspan) > 0:
				bit = '((.*)<2>|' + bitspan + ')'
				bitspan = ''
				bit += ' (' + bit1 + ':' + bit2 + ')'
			else:
				bit = '(' + bit1 + ':' + bit2 + ')'
		else:
			bitspan += bit1
		reg.append(bit)
	if len(bitspan) > 0:
		bit = '((.* - ' + bitspan + ')<2>|' + bitspan + ')'
		reg.append(bit)
	reg = ' '.join(reg) + '<' + str((ml-s)/3) + '>'
	return FST.re(reg)

def doit(f):
	'''do everything for a single language'''
	#read file
	F = open(os.path.join(loc, f),'r')
	t = F.read()
	F.close()
	t = t.strip()
	t = t.split('\n')
	#tokenize
	formlens = []
	data = []
	#extract bits
	for line in t:
		bits = line.split('\t')
		#do max word length calc
		formlens.append(len(bits[2]))
		data.append(tuple(bits))
	maxlen = max(formlens)
	#get alphabet:
	alpha = set()
	for lemma,_,word in data:
		for letter in lemma:
			alpha.add(letter)
		for letter in word:
			alpha.add(letter)
	alphaunion = '[' + ''.join(alpha) + ']'
	alphaunion = re.sub('-','\-',alphaunion)
	#make rules
	rules = {}
	i = 0
	while i < len(data):
		lemma,msd,word = data[i]
		edits = changes(lemma,word)
		rule = makerule(edits,maxlen)
		if msd in rules:
			rules[msd].append(rule)
		else:
			rules[msd] = [rule]
		i += 1
	print(f'{f[:-4]} rules ready')
	#get test/dev data
    #for dev
	g = open(os.path.join(loc, f[:-4] + '.dev'),'r')
	output = open(os.path.join(outpath, f[:-4] + '.test'),'w') # for creating output files
	t = g.read()
	g.close()
	t = t.strip()
	t = t.split('\n')
	total = len(t)
	#go through one by one
	correct = 0
	for line in t:
		lemma,msd,word = line.split('\t')
		best = lemma
		fixedlemma = re.sub("-","\-",lemma)
		#run lemma through approriate/msd WFST
		if msd in rules:
			mrules = rules[msd]
			res = {}
			for mrule in mrules:
				out = FST.re(fixedlemma).compose(mrule).words_nbest(1)
				if len(out) > 0:
					score = out[0][0]
					form = out[0][1]
					resform = ''
					for bit in form:
						if len(bit) == 1:
							resform += bit[0]
						elif bit[1] != '':
							resform += bit[1]
					# adjust the score by form frequency
					if resform in res:
						if score < res[resform]:
							res[resform] = score-0.3
						else:
							res[resform] -= 0.3
					else:
						res[resform] = score
			bestscore = 10000
			for r in res:
				if res[r] < bestscore:
					bestscore = res[r]
			bestset = []
			for r in res:
				if res[r] == bestscore:
					bestset.append(r)
			if len(bestset) == 0:
				best = lemma
			elif len(bestset) == 1:
				best = bestset[0]
			else:
				#choice: choose longest output
				longest = ""
				for b in bestset:
					if len(b) > len(longest):
						longest = b
				best = longest

		if best == word:
			correct += 1

		#check if the type of chosen best form is string. If not, print out the error message.
		if type(best) != str:
			print(best)
			print(f[:-4] + " " + lemma + " " + best[0] + " " + "there's something wrong about this")
		else:
			result = lemma + '\t' + msd + '\t' + best + '\n'
			output.write(result)

	output.close()
	#calculate score for each language
	print(f'{f[:-4]}: {correct/1000}')
	return (f[:-4],correct,total)

if __name__ == '__main__':
	files = os.listdir(loc)
	trainfiles = [f for f in files if f[-4:] == '.trn']
	cpus = multiprocessing.cpu_count()
	with multiprocessing.Pool(cpus-1) as p:
		allres = p.map(doit,trainfiles)
	totaltotal = 0
	totalcorrect = 0
	for res in allres:
		_,c,t = res
		totalcorrect += c
		totaltotal += t
	print(f'Overall accuracy: {totalcorrect/totaltotal}')
