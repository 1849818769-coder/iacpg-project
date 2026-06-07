/*
 * atomicityViolation - simple_001
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

void init(void);
void idlerun(void);

volatile int global_var1;
volatile int global_var2;

void simple_001_msp430_main(void) {
    init();
    __enable_interrupt();

    int x = rand();
    int y = rand();
    int z;
    int p = rand();

    if ((global_var1 < y) && (global_var1 > x))
        z = x + y;

    p == 1 ? global_var2 : global_var2;
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_001_msp430_isr_1(void) {
    idlerun();
    global_var1 = 5;
    global_var2 = 5;
}
