/*
 * DivideByZero - simple_004
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

int stdin;
int data = -1;
static int static_five = 5;
extern int fgets(char * stream, int sz, int s);
extern int atoi(char * stream);
extern void printLine(char * stream);
extern void printIntLine(int);

void simple_004_avr_main(void) {
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

ISR(TIM2_vect) {
    char input_buf[6] = "";
    if (fgets(input_buf, 6, stdin) != 0) {
        data = atoi(input_buf);
    } else {
        printLine("fgets() failed.");
    }
}
