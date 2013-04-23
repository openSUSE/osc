onintr -
if (! $?prompt || ! $?tcsh) goto end
if ($tcsh == 1) goto end
set rev=$tcsh:r
set rel=$rev:e
set pat=$tcsh:e
set rev=$rev:r
if ($rev > 5 && $rel > 1) then
    if ( -s /usr/share/osc/complete ) complete osc 'p@*@`\/usr/share/osc/complete`@'
    if ( -s /usr/lib64/osc/complete ) complete osc 'p@*@`\/usr/lib64/osc/complete`@'
    if ( -s /usr/lib/osc/complete   ) complete osc 'p@*@`\/usr/lib/osc/complete`@'
endif
end:
    onintr
