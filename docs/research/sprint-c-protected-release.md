# Sprint C: release protegido al terminar la Sprint

Decisión del operador, 9 de octubre de 2026: continuar el desarrollo ahora y
posponer la sincronización `develop`/`main` hasta terminar la Sprint. No se
autoriza por este documento ningún merge, bypass o cambio de reglas.

## Estado observado

`main`: `c8297139aaeed78c7951c91379983c414b181860`.
`develop`: `15e6d3494f6fedc6d61e6dbc14eaddc895b5e4e2`.
`git rev-list --left-right --count develop...main` dio **193 / 0**:
develop contiene todo main y tiene 193 commits exclusivos. No falta ahora un
commit de main. Es una observación, no una garantía sobre futuras actualizaciones.

El [ruleset24804548](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/rules/24804548)
está activo, dirigido solo a main, con restricciones de creación, actualización
y borrado. La API mostró required_status_checks con lista vacía y
strict_required_status_checks_policy=false. El PDF proporcionado por el operador
muestra bypass **Organization admin / Always allow**. Por tanto, no afirmar que
ningún otro usuario de la organización puede modificar main: los actores con
bypass y quienes puedan administrar reglas conservan capacidades relevantes.
Tampoco equivale la lista vacía a exigir nuestros cuatro checks de CI.

No se cambian ni debilitan las reglas. El acceso Write por sí solo no acredita
permiso de actualizar una rama restringida. Si la promoción queda bloqueada,
se presenta el requisito al operador, sin forzar ni usar bypass automáticamente.
La obligación interna de cuatro checks y autorización de merge se conserva
aunque no esté impuesta por ese ruleset.

## Secuencia de final de Sprint C

1. Cerrar y revisar E0, C2 y C3 según el
   [plan científico](mvp2-results-plan-20261009.md), con tablas y figuras.
   Obtener las autorizaciones individuales de merge a develop.
2. Volver a consultar los heads y reglas. Si main tiene commits exclusivos,
   abrir primero una PR de reconciliación **main hacia develop**, resolver
   conflictos sin descartar commits y ejecutar CI. No reescribir historia.
3. Cuando main sea ancestro de develop, abrir la PR de release **develop hacia
   main**, con changelog científico, manifiesto de evidencia y checks de código
   y manuscrito. Dejar ready antes de pedir autorización del merge.
4. Un merge normal crea un commit nuevo en main. Después de la promoción,
   comprobar nuevamente la ascendencia: no declarar ambos heads sincronizados
   solo porque la PR se cerró. Si hace falta, preparar un avance fast-forward
   de develop al merge de main sujeto a sus reglas y autorización; nunca force
   push. Si la política exige una PR adicional, explicar que dos direcciones
   no pueden representarse por una única PR.

No crear hoy esa PR de release ni mezclar main con las ramas experimentales.
La protección controla cambios de referencias, no convierte el repositorio
en un almacenamiento inmutable ni modifica los resultados históricos.
