onintr -
if (! $?prompt || ! $?tcsh) goto end
if ($tcsh == 1) goto end
set rev=$tcsh:r
set rel=$rev:e
set pat=$tcsh:e
set rev=$rev:r
if ($rev > 5 && $rel > 1) then
    complete osc 'p@*@`/usr/lib/osc/complete`@'
endif
end:
    onintr
