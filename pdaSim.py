import tkinter as tk
from tkinter import scrolledtext, Label, Frame, Text
import re
from automata.pda.npda import NPDA
from automata.pda.stack import PDAStack
from automata.pda.configuration import PDAConfiguration
from automata.base.exceptions import RejectionException
from functools import partial

def norm(txt):
    return re.sub("[^\S\r\n]", "", txt)
    
def removeNLs(txt):
    return re.sub("[\r\n]", "", txt)

def parseSpeed(s):
    try:
        value = int(s)
        if value <= 0:
             value = 1000
    except ValueError:
        return 1000;
    return value

class AsciiTree:
    
    BLTCORNER = "┌"
    BRTCORNER = "┐"
    BLBCORNER = "└"
    BRBCORNER = "┘"
    BHEDGE = "─"
    BVEDGE = "│"
    BTCONNECTOR = "┴"
    BBCONNECTOR = "┬"
    VEDGE = "│"
    HEDGE = "─"
    SCEDGE = "├"
    SEDGE = "└"
    EEDGE = "┐"
    CEDGE = "┬"
    
    def __init__(self, boxSize):
        self.content = ""
        self.boxSize = boxSize
        self.boxParts = (self.boxSize[1] >> 1, self.boxSize[1] - 1 - (self.boxSize[1] >> 1))
        self.boxTop = AsciiTree.BLTCORNER + self.boxParts[0] * AsciiTree.BHEDGE + AsciiTree.BTCONNECTOR + self.boxParts[1] * AsciiTree.BHEDGE + AsciiTree.BRTCORNER
        self.boxBottom = AsciiTree.BLBCORNER + self.boxParts[0] * AsciiTree.BHEDGE + AsciiTree.BBCONNECTOR + self.boxParts[1] * AsciiTree.BHEDGE + AsciiTree.BRBCORNER
        self.boxWidth = len(self.boxTop)
        self.lastLevel = ((0, 0), )
        return
        
    def createEdges(self, edgeGroups):
        content = ""
        if len(edgeGroups) == 0:
            return content
        lines = []
        for i, (pcol, toCols)in enumerate(edgeGroups):
            edgeLength = (toCols[-1] - pcol) * self.boxWidth
            edge = ""
            toColsCheck = set(((toCol - pcol) * self.boxWidth for toCol in toCols))
            if edgeLength == 0:
                edge = AsciiTree.VEDGE
            else:
                edge = "".join((AsciiTree.CEDGE if ichar in toColsCheck else char for ichar, char in enumerate(edgeLength * AsciiTree.HEDGE)))
                edge = (AsciiTree.SCEDGE if pcol == toCols[0] else AsciiTree.SEDGE) + edge[1:] + AsciiTree.EEDGE
            prefix = (pcol * self.boxWidth + self.boxParts[0] + 1) * " "
            line = prefix + edge 
            lines.append(line)
        #norm
        maxLength = max((len(line) for line in lines))
        lines = [line + (maxLength - len(line)) * " " for line in lines]
        #scan from bottom to top
        for i in range(1, len(lines)):
            prevLine = lines[i-1]
            line = lines[i]
            toFinish = set([AsciiTree.SCEDGE, AsciiTree.SEDGE, AsciiTree.VEDGE])
            lines[i] = "".join([AsciiTree.VEDGE if char == " " and prevLine[ichar] in toFinish else char for ichar, char in enumerate(line)])
        lines.reverse()
        #scan again from top to bottom
        for i in range(1, len(lines)):
            prevLine = lines[i-1]
            line = lines[i]
            toFinish = set([AsciiTree.SCEDGE, AsciiTree.EEDGE, AsciiTree.VEDGE, AsciiTree.CEDGE])
            lines[i] = "".join([AsciiTree.VEDGE if char == " " and prevLine[ichar] in toFinish else char for ichar, char in enumerate(line)])
        return "\n".join(lines)
        
    def addLevel(self, items):
        topLine = ""
        midLines = [""] * self.boxSize[0]
        bottomLine = ""
        nextCol = 0
        level = []
        edgeGroups = []
        for parent, pcol in self.lastLevel:
            toCols = []
            if parent not in items:
                continue
            for i, (child, data) in enumerate(items[parent]):
                col = max(pcol + i, nextCol)
                level.append((child, col))
                toCols.append(col)
                df = col - nextCol
                nextCol = col + 1
                topLine += " " * df * self.boxWidth + self.boxTop
                for j in range(self.boxSize[0]):
                    lineData = data[j][:self.boxSize[1]]
                    lineData = lineData + (self.boxSize[1] - len(lineData)) * " "
                    midLines[j] += " " * df * self.boxWidth + AsciiTree.BVEDGE + lineData + AsciiTree.BVEDGE
                bottomLine += " " * df * self.boxWidth + self.boxBottom
            if len(toCols) > 0:
                edgeGroups.append((pcol, toCols))
        content = self.createEdges(edgeGroups) + "\n" + topLine + "\n" + "\n".join(midLines) + "\n" + bottomLine + "\n"
        self.content += content
        self.lastLevel = tuple(level)
        return content

class MyNPDA(NPDA):
    
    def read_input_stepwise(self, input_str):
        """
        Check if the given string is accepted by this NPDA.
        Yield the NPDA's current configurations at each step.
        """
        current_configurations = set()
        initial_configuration = PDAConfiguration(
            self.initial_state,
            input_str,
            PDAStack([self.initial_stack_symbol])
        )
        initial_configuration.cid = 0
        initial_configuration.pcid = 0
        current_configurations.add(initial_configuration)

        yield current_configurations

        cid = 1
        while current_configurations:
            new_configurations = set()
            for config in current_configurations:
                if self._has_accepted(config):
                    # One accepting configuration is enough.
                    return
                next_configurations = set()
                if config.remaining_input or self._has_lambda_transition(config.state, config.stack.top()):
                    next_configurations = self._get_next_configurations(config)
                for next_conf in next_configurations:
                    next_conf.cid = cid
                    cid += 1
                    next_conf.pcid = config.cid
                new_configurations.update(
                    next_configurations
                )
            current_configurations = new_configurations
            yield current_configurations

        raise RejectionException(
            'the NPDA did not reach an accepting configuration'
        )

class Automaton:
    
    def __init__(self, parser):
        self.parser = parser
        self.npda = None
        self.steps = None
        self.asciiTree = AsciiTree((3,20))
        self.canStep = True
        self.simulating = False
        return
        
    def stop(self, text_area_C=None):
        self.npda = None
        self.steps = None
        if text_area_C is not None:
            text_area_C.delete('1.0', 'end')
        self.canStep = True
        self.simulating = False
        self.asciiTree = AsciiTree((3,20))
        return
        
    def initialize(self, txtAreaT, txtAreaF, txtAreaI):
        txtTrans = txtAreaT.get("1.0", "end")
        txtF = txtAreaF.get("1.0", "end")
        txtI = txtAreaI.get("1.0", "end")
        definition = self.parser.parse(txtTrans, txtF)
        print(definition)
        self.npda = MyNPDA(**definition)
        self.steps = self.npda.read_input_stepwise(removeNLs(txtI))
        return
        
    def step(self, txtAreaT, txtAreaF, txtAreaI, text_area_C):
        if(self.canStep == False):
            return
        if self.steps is None:
            self.initialize(txtAreaT, txtAreaF, txtAreaI)
        try:
            confs = next(self.steps)
            items = {}
            for conf in confs:
                if conf.pcid not in items:
                    items[conf.pcid] = []
                items[conf.pcid].append((conf.cid, ("S:" + conf.state, "V:" + conf.remaining_input, "Z:" + "".join(conf.stack))))
            if len(items) > 0:
                treePart = self.asciiTree.addLevel(items)
                #text_area_C.delete('1.0', 'end')
                text_area_C.insert(tk.END, treePart)
            print(confs)
        except StopIteration:
            print("ACCEPTED!!!")
            text_area_C.insert(tk.END, ("\n" + "─"*11 + "\n"*2) + "ACCEPTED!!!")
            self.canStep = False
        except RejectionException:
            print("REJECTED!!!")
            text_area_C.insert(tk.END, ("\n" + "─"*11 + "\n"*2) + "REJECTED!!!")
            self.canStep = False
        text_area_C.see(tk.END)
        return

class Parser:
    
    def __init__(self):
        return
        
    def parse(self, txtTrans, txtF):
        transitions = {}
        states = set()
        inputSymbols = set()
        stackSymbols = set()
        
        normedTrans = norm(txtTrans)
        
        matches = re.finditer("d\(([a-z]\d*),(.?),([A-Z]\d*)\)=\(([a-z]\d*),(([A-Z]\d*)*)\)", normedTrans)
        for match in matches:
            
            state = match.group(1)
            inputSymbol = match.group(2)
            stackTop = match.group(3)
            newState = match.group(4)
            pushToStack = tuple(re.findall("[A-Z]\d*", match.group(5)))
           
            states.add(state)
            inputSymbols.add(inputSymbol)
            stackSymbols.add(stackTop)
            stackSymbols.update(pushToStack)
           
            if state not in transitions:
                transitions[state] = {}
            if inputSymbol not in transitions[state]:
                transitions[state][inputSymbol] = {}
            if stackTop not in transitions[state][inputSymbol]:
                transitions[state][inputSymbol][stackTop] = set()
            transitions[state][inputSymbol][stackTop].add((newState, pushToStack))
        
        inputSymbols.discard('')
        stackSymbols.add('Z0')
        states.add('q0')
        
        normedF = norm(txtF)
        match = re.match("\{(([a-z]\d*)(,[a-z]\d*)*)\}", normedF)
        finalStates = set(match.group(1).split(',')) if match is not None else set()
        
        states.add('q0')
        states.update(finalStates)
        
        definition = {
            'states':states,
            'input_symbols':inputSymbols,
            'stack_symbols':stackSymbols,
            'transitions':transitions,
            'initial_state':'q0',
            'initial_stack_symbol':'Z0',
            'final_states':finalStates,
            'acceptance_mode':'final_state'
        }
        return definition
  
if __name__=="__main__":
    """
    asciiTree = AsciiTree((3,20))
    asciiTree.addLevel({0:((0,("S:q0","V:a","Z:A")),)})
    asciiTree.addLevel({0:((1, ("S:q0","V:a","Z:A")),(2, ("S:q0","V:a","Z:A")),(3, ("S:q0","V:a","Z:A")))})
    print(asciiTree.content)
    import sys
    sys.exit(0)
    """
    
    # Creating tkinter main window
    win = tk.Tk()
    win.title("PDA Sim")

    parser = Parser()
    automaton = Automaton(parser)

    font = ("Consolas", 12)

    label = Label(text = "Definícia", anchor="w", font=font)
    label.grid(row=0, column=0, sticky="w", padx=10, pady=(10,0))
    text_area = scrolledtext.ScrolledText(
        win, 
        wrap = tk.WORD, 
        width = 40, 
        height = 9, 
        font = font
    )
    text_area.grid(row = 1, column = 0, padx = 10)
    text_area.insert(tk.INSERT, "\n".join((
        "M = (K, S, T, d, q0, Z0, F)\n",
        "K je konečná množina stavov",
        "S je vstupná abeceda",
        "T je zásobníková abeceda",
        "d je prechodová funkcia",
        "q0 je počiatočný stav",
        "Z0 je počiatočný zásobníkový symbol",
        "F je množina koncových stavov"
    )))
    text_area.config(state=tk.DISABLED)

    label = Label(text = "F", anchor="w", font=font)
    label.grid(row=2, column=0, sticky="w", padx=10, pady=(10,0))
    text_area_F = scrolledtext.ScrolledText(
        win, 
        wrap = tk.WORD, 
        width = 40, 
        height = 1, 
        font = font
    )
    text_area_F.grid(row = 3, column = 0, padx = 10)
    text_area_F.insert(tk.INSERT, "{f1, f2}")

    label = Label(text = "Prechodové funkcie", anchor="w", font=font)
    label.grid(row=4, column=0, sticky="w", padx=10, pady=(10,0))
    text_area_T = scrolledtext.ScrolledText(
        win, 
        wrap = tk.WORD, 
        width = 40, 
        height = 10, 
        font = font
    )
    text_area_T.grid(row = 5, column = 0, pady = (0,10), padx = 10)

    label = Label(text = "Priebeh", anchor="w", font=font)
    label.grid(row=0, column=1, sticky="w", padx=10, pady=(10,0))

    cframe = Frame(win)
    vbar = tk.Scrollbar(cframe)
    vbar.pack (side = tk.RIGHT, fill = "y")
    hbar = tk.Scrollbar(cframe, orient = tk.HORIZONTAL)
    hbar.pack (side = tk.BOTTOM, fill = "x")
    text_area_C = tk.Text(
        cframe, 
        width = 110,
        yscrollcommand = vbar.set,
        xscrollcommand = hbar.set, 
        wrap = "none",
        font = ("Consolas", 8)
    )
    text_area_C.pack(expand = 1, fill = tk.BOTH)
    hbar.config(command = text_area_C.xview)
    vbar.config(command = text_area_C.yview)
    cframe.grid(row = 1, column = 1, rowspan=7, pady = (0,10), padx = 10, sticky="ns")

    label = Label(text = "Vstup", anchor="w", font=font)
    label.grid(row=6, column=0, sticky="w", padx=10)
    text_area_I = scrolledtext.ScrolledText(
        win, 
        wrap = tk.WORD, 
        height = 2,
        width = 40,
        font = font
    )
    text_area_I.grid(row = 7, column = 0, pady = (0,10), padx = 10)

    bframe = Frame(win)
    bframe.grid(row=8, column=0, columnspan=2, sticky="nsew")

    button1=tk.Button(bframe, text="Stop", command=lambda: automaton.stop(text_area_C))
    button1.grid(row = 0, column = 0, pady = (0,10), padx = (10,0))

    button1=tk.Button(bframe, text="Krok", command=lambda: automaton.step(text_area_T, text_area_F, text_area_I, text_area_C))
    button1.grid(row = 0, column = 1, pady = (0,10))

    def __simuluj(speed):
        if automaton.simulating == True  and automaton.canStep == True:
            automaton.step(text_area_T, text_area_F, text_area_I, text_area_C);
            text_area_C.after(speed,lambda: __simuluj(speed))
    def simuluj():
        if automaton.simulating == False:
            automaton.simulating = True
            speed = parseSpeed(simSpeedTxt.get())
            __simuluj(speed)

    simButton=tk.Button(bframe, text="Simuluj", command=simuluj)
    simButton.grid(row = 0, column = 2, pady = (0,10))
    
    simSpeedTxt = tk.Entry(bframe)
    simSpeedTxt.insert(0,"1000")
    simSpeedTxt.grid(row = 0,column = 3,pady = (0,10))


    # Placing cursor in the text area
    text_area_T.focus()
    win.resizable(False, False)
    win.mainloop()