/*
 * atomicityViolation - simple_001
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void init(void);
void idlerun(void);

volatile int global_var1;
volatile int global_var2;

void simple_001_avr_main(void) {
    init();
    sei();

    int x = rand();
    int y = rand();
    int z;
    int p = rand();

    if ((global_var1 < y) && (global_var1 > x))
        z = x + y;

    p == 1 ? global_var2 : global_var2;
}

ISR(TIMER2_OVF_vect) {
    idlerun();
    global_var1 = 5;
    global_var2 = 5;
}
