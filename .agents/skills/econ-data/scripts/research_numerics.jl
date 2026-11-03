# Independent Julia sparse solve: (I - discount * Q) v = sin((0:n-1)/100).
using SparseArrays, LinearAlgebra
n = parse(Int, ARGS[1]); birth = parse(Float64, ARGS[2]); death = parse(Float64, ARGS[3]); discount = parse(Float64, ARGS[4])
n >= 2 && birth >= 0 && death >= 0 && discount >= 0 || error("invalid generator parameters")
diagonal = vcat(-birth, fill(-birth-death, n-2), -death)
Q = spdiagm(-1 => fill(death, n-1), 0 => diagonal, 1 => fill(birth, n-1))
A = sparse(I, n, n) - discount * Q
rhs = sin.((0:n-1) ./ 100)
v = A \ rhs
println(VERSION)
println(join((maximum(abs.(sum(Q, dims=2))), maximum(abs.(A*v-rhs))), ','))
println(join(v, ','))
