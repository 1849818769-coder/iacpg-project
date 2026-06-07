/*
 * DivideByZero - simple_004
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

int stdin;
int data = -1;
static int static_five = 5;
extern int fgets(char * stream, int sz, int s);
extern int atoi(char * stream);
extern void printLine(char * stream);
extern void printIntLine(int);

void simple_004_msp430_main(void) {
    if (static_five == 5) {
        {
            char input_buf[6] = "";
            if (fgets(input_buf, 6, stdin) != 0) {
                data = atoi(input_buf);
            } else {
                printLine("fgets() failed.");
            }
        }
    } else {
        data = 7;
    }
    if (static_five == 5) {
        if (data != 0) {
            printIntLine(100 / data);
        } else {
            printIntLine(100);
        }
    }
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_004_msp430_isr(void) {
    char input_buf[6] = "";
    if (fgets(input_buf, 6, stdin) != 0) {
        data = atoi(input_buf);
    } else {
        printLine("fgets() failed.");
    }
}
