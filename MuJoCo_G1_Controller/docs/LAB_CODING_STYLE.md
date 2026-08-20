# Lab Coding Style

## Brace Style

Opening braces are placed on the next line.

```cpp
for(...)
{
    std::cout << "for" << std::endl;
    if(...)
    {
        std::cout << "if" << std::endl;
    }
}
```

## Variables

Variables use lowercase snake case and should be noun phrases.

```cpp
int boundingbox_value;      // OK
int get_boundingbox_value;  // NG
```

Do not use consecutive underscores, prefix underscores, or suffix underscores.

```cpp
int boundingbox_value;    // OK
int boundingbox__value;   // NG
int _boundingbox_value;   // NG
int boundingbox_value_;   // NG
```

Compound terms that have one combined meaning are kept together.

```cpp
int boundingbox_value;   // OK
int bounding_box_value;  // NG
```

## Functions

Functions start with a verb and use PascalCase.

```cpp
int GetBoundingboxValue();      // OK
int BoundingboxValue();         // NG
int get_boundingbox_value();    // NG
```

Conversion, parsing, and coordinate-transform functions using `To` may omit the leading verb.

```cpp
double DegreeToRadian();  // OK
void GlobalToLocal();     // OK
```

Do not add redundant conversion verbs in these cases.

```cpp
double ConvertDegreeToRadian();  // NG
void ComputeGlobalToLocal();     // NG
```

## Acronyms

Acronyms are written in uppercase.

```cpp
void GetFTSensorData();   // OK
void GetIMUSensorData();  // OK
```

## Current Project Note

This style should be applied first to C++ bridge/controller code that connects Unity or MuJoCo targets to the Unitree low-level command structure.

Unity C# scripts may keep Unity/C# API naming where necessary, but new project-specific C++ code should follow this style.
