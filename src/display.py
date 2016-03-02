#!/bin/python

import curses

def main(screen):
     curses.start_color()
     curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLUE)
     curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)

     screen.bkgd(curses.color_pair(1))
     screen.refresh()

     screen.addstr(0, 0, "STATUS: connecting...",
                   curses.A_REVERSE)

     win = curses.newwin(5, 20, 5, 5)
     win.bkgd(curses.color_pair(2))
     win.box()
     win.addstr(2, 2, "Hallo, Welt!")
     win.refresh()

     c = screen.getch()

try:
     curses.wrapper(main)
except KeyboardInterrupt:
     print "Got KeyboardInterrupt exception. Exiting..."
     exit() 

